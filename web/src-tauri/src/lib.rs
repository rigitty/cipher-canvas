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
    let parent_pid = std::process::id();
    let root = project_root();

    // 1. Try standalone compiled engine executable
    let exe_candidates = [
        root.join("dist").join("cipher-engine.exe"),
        root.join("cipher-engine.exe"),
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("cipher-engine.exe")))
            .unwrap_or_default(),
    ];

    for exe in exe_candidates {
        if exe.exists() {
            let mut command = Command::new(&exe);
            command
                .arg("--parent-pid")
                .arg(parent_pid.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null());

            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                command.creation_flags(HIDE_WINDOW_FLAG);
            }

            if let Ok(child) = command.spawn() {
                return Some(child);
            }
        }
    }

    // 2. Dev mode fallback: run via python interpreter
    let mut command = Command::new("python");
    command
        .arg("server.py")
        .arg("--parent-pid")
        .arg(parent_pid.to_string())
        .current_dir(root)
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

#[tauri::command]
async fn read_file_binary(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendState(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![save_file, read_file_binary])
        .setup(|app| {
            if let Some(win) = app.get_webview_window("main") {
                if let Ok(icon) = tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png")) {
                    let _ = win.set_icon(icon);
                } else if let Some(icon) = app.default_window_icon() {
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
        .run(|app_handle, event| match event {
            RunEvent::Exit | RunEvent::ExitRequested { .. } => {
                let backend = app_handle.state::<BackendState>();
                let mut guard = backend.0.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
            _ => {}
        });
}