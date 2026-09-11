use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

const HIDE_WINDOW_FLAG: u32 = 0x0800_0000;

struct BackendState(Mutex<Option<Child>>);

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn spawn_backend() -> Option<Child> {
    let mut command = Command::new("python");
    command
        .arg("server.py")
        .current_dir(project_root())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(HIDE_WINDOW_FLAG);
    }

    command.spawn().ok()
}

#[tauri::command]
async fn save_file(
    file_name: String,
    data: Vec<u8>,
    filter_name: Option<String>,
    filter_extensions: Option<Vec<String>>,
) -> Result<String, String> {
    let mut dialog = rfd::AsyncFileDialog::new()
        .set_title("Save File")
        .set_file_name(&file_name);
    if let (Some(name), Some(extensions)) = (filter_name, filter_extensions) {
        dialog = dialog.add_filter(&name, &extensions);
    }
    let handle = dialog
        .save_file()
        .await
        .ok_or_else(|| "save cancelled".to_string())?;
    handle
        .write(&data)
        .await
        .map_err(|err| err.to_string())?;
    Ok(handle.path().to_string_lossy().to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![save_file])
        .setup(|app| {
            if let Some(icon) = app.default_window_icon() {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.set_icon(icon.clone());
                }
            }
            let child = spawn_backend();
            if child.is_none() {
                eprintln!("warning: failed to start the python engine server");
            }
            *app.state::<BackendState>().0.lock().unwrap() = child;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Cipher Canvas application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                let backend = app_handle.state::<BackendState>();
                let mut guard = backend.0.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        });
}