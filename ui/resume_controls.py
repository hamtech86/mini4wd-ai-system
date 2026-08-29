"""UI controls for safe recipe pause/resume."""

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QGroupBox, QHBoxLayout, QMessageBox, QPushButton


class ResumeWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, controller, recipe, instance_id):
        super().__init__()
        self.controller = controller
        self.recipe = recipe
        self.instance_id = instance_id

    def run(self):
        try:
            result = self.controller.resume_from_checkpoint(
                self.recipe, instance_id=self.instance_id
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def install_resume_controls(window):
    """Install PAUSE/RESUME and raw-log verification controls."""
    if hasattr(window, "pause_button"):
        return

    window.resume_worker = None
    window.pause_button = QPushButton("PAUSE")
    window.resume_button = QPushButton("RESUME")
    window.pause_button.setEnabled(False)
    window.resume_button.setEnabled(False)
    window.pause_button.setMinimumHeight(32)
    window.resume_button.setMinimumHeight(32)
    window.pause_button.clicked.connect(window.pause_run)
    window.resume_button.clicked.connect(window.resume_run)

    runtime_group = None
    result_group = None
    for group in window.findChildren(QGroupBox):
        if group.title().startswith("②"):
            runtime_group = group
        elif group.title() == "③ 結果":
            result_group = group

    if runtime_group is not None and runtime_group.layout() is not None:
        row = QHBoxLayout()
        row.addWidget(window.pause_button)
        row.addWidget(window.resume_button)
        runtime_group.layout().addItem(row)

    window.raw_log_copy_button = QPushButton("生ログをクリップボードに登録")
    window.raw_log_copy_button.setEnabled(False)
    window.raw_log_copy_button.setMinimumHeight(36)
    window.raw_log_copy_button.clicked.connect(lambda: copy_raw_log(window))

    if result_group is not None and result_group.layout() is not None:
        row = QHBoxLayout()
        row.addWidget(window.raw_log_copy_button)
        result_group.layout().addItem(row)

    if hasattr(window, "timer"):
        window.timer.timeout.connect(window.refresh_resume_state)


def _raw_log_controller(window):
    controller = getattr(window, "breakin_controller", None)
    if controller is None:
        return None
    return getattr(controller, "serial_controller", None) or getattr(controller, "serial", None)


def copy_raw_log(window):
    controller = _raw_log_controller(window)
    raw = getattr(controller, "last_raw_data", None) if controller is not None else None
    if not raw:
        QMessageBox.information(window, "生ログ", "コピー可能なDATA生ログがまだありません。")
        return
    QApplication.clipboard().setText(raw)
    window.raw_log_copy_button.setText("生ログを登録済み")


def _checkpoint_for_window(window):
    controller = getattr(window, "breakin_controller", None)
    return controller.resume_checkpoint() if controller and hasattr(controller, "resume_checkpoint") else None


def _checkpoint_matches(window, checkpoint):
    if not checkpoint:
        return False
    instance_id = window.instance.currentData()
    recipe_key = window.recipe.currentData()
    if instance_id is None or recipe_key == getattr(window, "BENCHMARK_KEY", None):
        return False
    recipe = window.recipe_engine.get(recipe_key) if recipe_key else None
    if recipe is None:
        return False
    return (
        str(checkpoint.get("recipe", "")).upper() == str(recipe.name).upper()
        and checkpoint.get("instance_id") == instance_id
    )


def refresh_resume_state(window):
    controller = getattr(window, "breakin_controller", None)
    if controller is None or not hasattr(window, "pause_button"):
        return
    running = bool(getattr(controller, "running", False))
    paused = bool(getattr(controller, "paused", False))
    checkpoint = _checkpoint_for_window(window)
    resumable = _checkpoint_matches(window, checkpoint)

    window.pause_button.setEnabled(running and not paused)
    window.resume_button.setEnabled(paused or (not running and resumable))

    raw_controller = _raw_log_controller(window)
    if hasattr(window, "raw_log_copy_button"):
        window.raw_log_copy_button.setEnabled(bool(getattr(raw_controller, "last_raw_data", None)))

    if paused:
        window.run_state.setText("PAUSED / RESUME AVAILABLE")
        phase = getattr(controller, "current_phase", None)
        if phase is not None:
            elapsed = float(controller.phase_elapsed_sec()) if hasattr(controller, "phase_elapsed_sec") else 0.0
            window.progress["ELAPSED"].setText(f"{elapsed:.1f} s / PAUSED")
    elif not running and resumable and window.result["STATUS"].text() not in ("BREAK-IN COMPLETE", "BENCHMARK COMPLETE"):
        window.run_state.setText("RESUME AVAILABLE")


def pause_run(window):
    controller = getattr(window, "breakin_controller", None)
    if controller is None:
        return
    try:
        if controller.pause():
            window.run_state.setText("PAUSED / CHECKPOINT SAVED")
            window.database_status.setText("DATABASE: NOT UPDATED / RECIPE PAUSED")
    except Exception as exc:
        QMessageBox.critical(window, "PAUSE", f"一時停止に失敗しました。\n{type(exc).__name__}: {exc}")


def resume_run(window):
    controller = getattr(window, "breakin_controller", None)
    if controller is None:
        return
    checkpoint = _checkpoint_for_window(window)
    if not _checkpoint_matches(window, checkpoint):
        QMessageBox.warning(window, "RESUME", "現在選択中のRecipe / Motor Instanceに一致する再開状態がありません。")
        return

    recipe = window.recipe_engine.get(window.recipe.currentData())
    instance_id = window.instance.currentData()
    window.resume_worker = ResumeWorker(controller, recipe, instance_id)
    window.resume_worker.completed.connect(lambda data: window.complete(data, False))
    window.resume_worker.failed.connect(window.failed)
    window.resume_worker.finished.connect(lambda: setattr(window, "resume_worker", None))
    window.start.setEnabled(False)
    window.manager.setEnabled(False)
    window.instance.setEnabled(False)
    window.recipe.setEnabled(False)
    window.stop.setEnabled(True)
    window.pause_button.setEnabled(False)
    window.resume_button.setEnabled(False)
    window.result["STATUS"].setText("RESUMING")
    window.run_state.setText("RESUMING FROM CHECKPOINT...")
    window.timer.start()
    window.resume_worker.start()


def bind_resume_api(window_class):
    window_class.pause_run = pause_run
    window_class.resume_run = resume_run
    window_class.refresh_resume_state = refresh_resume_state
    return window_class
