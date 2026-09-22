"""Desktop entry point and opt-in packaged startup check (no crafting actions)."""
import json
import os
from pathlib import Path
import sys
import traceback


def self_test(report_path):
    # Keep verification settings isolated from real customer settings.
    report_path = Path(report_path).resolve()
    os.environ['LOCALAPPDATA'] = str(report_path.parent / 'test-user-data')
    report = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False))}
    app = None
    try:
        import pororbbot_ctk as program
        import keyboard
        assert program._FULL_EQUIPMENT_TYPES, 'Embedded equipment data is empty'
        assert program._AFFIX_INDEX, 'Embedded affix index is empty'
        app = program.MainApp()
        callback_errors = []
        app.app.report_callback_exception = lambda *args: callback_errors.append(
            ''.join(traceback.format_exception(*args)))
        app.app.after(1500, app.app.quit)
        app.run()
        assert not callback_errors, '\n'.join(callback_errors)
        assert not app.bot.running, 'Startup must not begin crafting'
        app.bot.save_config()
        restored = program.PoeOrbBotBase()
        assert restored.config == app.bot.config, 'Configuration round-trip failed'
        report.update(ok=True, equipment_types=len(program._FULL_EQUIPMENT_TYPES),
                      affix_groups=sum(len(v) for v in program._AFFIX_INDEX.values()),
                      config_path=app.bot.config_file, window_title=app.app.title())
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if app is not None:
            import keyboard
            keyboard.unhook_all()
            app.app.destroy()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        sys.exit(self_test(sys.argv[2]))
    from pororbbot_ctk import MainApp
    MainApp().run()
