#!/usr/bin/env python3
import os
import sys
import shlex
import shutil

UID = os.getuid()
CMD_FILE = f"/tmp/.sudo-uac-cmd-{UID}"


def is_askpass_mode():
    try:
        with open(f"/proc/{os.getppid()}/comm") as f:
            if f.read().strip() == "sudo":
                return True
    except Exception:
        pass
    return (
        len(sys.argv) >= 2
        and os.environ.get("SUDO_ASKPASS") == os.path.abspath(sys.argv[0])
    )


def launch():
    me = os.path.abspath(sys.argv[0])
    os.environ["SUDO_ASKPASS"] = me
    os.environ["SUDO_ASKPASS_REQUIRE"] = "force"
    
    try:
        with open(CMD_FILE, "w") as f:
            f.write(" ".join(sys.argv[1:]))
    except Exception:
        pass

    try:
        os.execvp("sudo", ["sudo", "-A"] + sys.argv[1:])
    except Exception:
        sys.exit(1)


def prompt_and_launch():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    dialog = Gtk.Dialog(title="sudo-uac")
    dialog.set_default_size(500, -1)
    dialog.add_buttons("取消", Gtk.ResponseType.CANCEL, "确定", Gtk.ResponseType.OK)
    
    box = dialog.get_content_area()
    box.set_spacing(10)
    box.set_margin_top(14)
    box.set_margin_bottom(14)
    box.set_margin_start(16)
    box.set_margin_end(16)

    title = Gtk.Label()
    title.set_markup("<b>请输入要以管理员权限执行的命令：</b>")
    title.set_xalign(0)
    box.pack_start(title, False, False, 0)

    entry = Gtk.Entry()
    entry.set_text("apt update")
    entry.connect("activate", lambda w: dialog.response(Gtk.ResponseType.OK))
    box.pack_start(entry, False, False, 0)

    dialog.show_all()
    resp = dialog.run()
    cmd = entry.get_text().strip() if resp == Gtk.ResponseType.OK else ""
    dialog.destroy()

    if not cmd:
        sys.exit(1)

    try:
        args = shlex.split(cmd)
        me = os.path.abspath(sys.argv[0])
        os.execv(me, [me] + args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


def play_uac_sound():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    sound_file = os.path.join(script_dir, "windows-10-uac.mp3")
    
    if not os.path.exists(sound_file):
        return

    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        player = Gst.ElementFactory.make("playbin", "player")
        if player:
            player.set_property('uri', f'file://{sound_file}')
            player.set_state(Gst.State.PLAYING)
            globals()['_uac_player'] = player
            return
    except Exception:
        pass


def askpass():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk

    is_error = os.environ.get("UAC_ERROR") == "1"
    
    try:
        with open(CMD_FILE) as f:
            command = f.read().strip()
    except Exception:
        command = ""

    # 判断是否为“未知发布者”（非系统目录下的程序）
    is_unknown = False
    if command:
        prog_name = command.split()[0]
        prog_path = shutil.which(prog_name)
        # 如果不是系统标准路径，就当做未知发布者
        if not prog_path or not prog_path.startswith(("/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin")):
            is_unknown = True
    else:
        is_unknown = True

    class UAC(Gtk.Window):
        def __init__(self):
            super().__init__(title="用户账户控制")
            self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
            self.set_default_size(540, 340)
            self.set_resizable(False)
            self.set_keep_above(True) 
            self.set_decorated(False)
            self.connect("destroy", lambda w: os._exit(1))
            self.connect("key-press-event", self.on_key)

            self.outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.outer.get_style_context().add_class("uac-outer")
            self.add(self.outer)

            # ================= 1. 顶部标题栏 =================
            self.header_box = Gtk.EventBox()
            # 动态判断颜色：未知程序为黄，系统程序为蓝
            if is_unknown:
                self.header_box.get_style_context().add_class("uac-header-yellow")
            else:
                self.header_box.get_style_context().add_class("uac-header-blue")
            
            self.header_box.connect("button-press-event", self.on_drag)
            
            header_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            
            title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            t_lbl = Gtk.Label()
            # 黄色背景配黑字，蓝色背景配白字
            t_color = "#000000" if is_unknown else "white"
            t_lbl.set_markup(f"<span color='{t_color}' font='9'>用户账户控制</span>")
            t_lbl.set_margin_start(12)
            t_lbl.set_margin_top(6)
            t_lbl.set_margin_bottom(6)
            title_bar.pack_start(t_lbl, False, False, 0)
            
            close_btn = Gtk.Button(label="✕")
            close_btn.set_relief(Gtk.ReliefStyle.NONE)
            close_btn.get_style_context().add_class("uac-close")
            close_btn.connect("clicked", lambda w: os._exit(1))
            title_bar.pack_end(close_btn, False, False, 0)
            
            header_inner.pack_start(title_bar, False, False, 0)

            q_lbl = Gtk.Label()
            if is_unknown:
                q_lbl.set_markup("<span font='14' color='#000000'>你要允许来自未知发布者的此应用对你的设备进行更改吗？</span>")
            else:
                q_lbl.set_markup("<span font='14' color='#000000'>你要允许此应用对你的设备进行更改吗？</span>")
            
            q_lbl.set_xalign(0)
            q_lbl.set_line_wrap(True)
            q_lbl.set_margin_start(16)
            q_lbl.set_margin_end(16)
            q_lbl.set_margin_bottom(16)
            header_inner.pack_start(q_lbl, False, False, 0)

            self.header_box.add(header_inner)
            self.outer.pack_start(self.header_box, False, False, 0)

            # ================= 2. 主内容区 =================
            content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            content_box.set_margin_top(16)
            content_box.set_margin_bottom(16)
            content_box.set_margin_start(20)
            content_box.set_margin_end(20)
            content_box.get_style_context().add_class("uac-content")

            app_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            # 未知程序用普通的可执行文件图标，系统程序用终端图标
            icon_name = "application-x-executable" if is_unknown else "utilities-terminal"
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
            icon.set_pixel_size(36)
            
            app_lbl = Gtk.Label()
            app_lbl.set_markup(f"<span font='11' color='#000000'>{command or '未知程序'}</span>")
            app_lbl.set_xalign(0)
            app_lbl.set_line_wrap(True)
            app_row.pack_start(icon, False, False, 0)
            app_row.pack_start(app_lbl, False, False, 0)
            content_box.pack_start(app_row, False, False, 0)

            # 发布者和文件源（如果未知就显示多余的信息）
            pub_lbl = Gtk.Label()
            if is_unknown:
                pub_lbl.set_markup("<span font='10' color='#000000'>发布者: 未知</span>")
            else:
                pub_lbl.set_markup("<span font='10' color='#000000'>已验证的发布者: Linux 系统</span>")
            pub_lbl.set_xalign(0)
            content_box.pack_start(pub_lbl, False, False, 0)

            if is_unknown:
                src_lbl = Gtk.Label()
                src_lbl.set_markup("<span font='10' color='#000000'>文件源: 此计算机上的硬盘驱动器</span>")
                src_lbl.set_xalign(0)
                content_box.pack_start(src_lbl, False, False, 0)

            pw_prompt = Gtk.Label()
            pw_prompt.set_markup("<span font='10' color='#333333'>请输入管理员密码以进行验证：</span>")
            pw_prompt.set_xalign(0)
            pw_prompt.set_margin_top(4)
            content_box.pack_start(pw_prompt, False, False, 0)

            pw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            self.pw = Gtk.Entry()
            self.pw.set_visibility(False)
            self.pw.set_placeholder_text("管理员密码")
            self.pw.get_style_context().add_class("uac-entry")
            self.pw.connect("activate", lambda w: self.confirm())
            pw_row.pack_start(self.pw, True, True, 0)
            content_box.pack_start(pw_row, False, False, 0)

            self.error_lbl = Gtk.Label()
            self.error_lbl.set_xalign(0)
            if is_error:
                self.error_lbl.set_markup("<span font='9' foreground='#c0392b'>密码错误，请重试</span>")
            else:
                self.error_lbl.set_markup("")
            content_box.pack_start(self.error_lbl, False, False, 0)

            self.outer.pack_start(content_box, True, True, 0)

            # ================= 3. 底部按钮区 =================
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
            btn_box.get_style_context().add_class("uac-btn-box")

            yes_btn = Gtk.Button(label="是")
            yes_btn.set_hexpand(True)
            yes_btn.get_style_context().add_class("uac-btn")
            yes_btn.connect("clicked", lambda w: self.confirm())
            
            no_btn = Gtk.Button(label="否")
            no_btn.set_hexpand(True)
            no_btn.get_style_context().add_class("uac-btn")
            no_btn.connect("clicked", lambda w: os._exit(1))

            btn_box.pack_start(yes_btn, True, True, 0)
            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            sep.get_style_context().add_class("uac-sep")
            btn_box.pack_start(sep, False, False, 0)
            btn_box.pack_start(no_btn, True, True, 0)
            self.outer.pack_start(btn_box, False, False, 0)

            # ================= CSS =================
            css = Gtk.CssProvider()
            css_data = """
                .uac-outer { background-color: #f0f0f0; border: 1px solid #999; }
                .uac-header-blue { background-color: #1e72c1; }
                .uac-header-yellow { background-color: #ffb900; } /* Win10 黄色警告色 */
                .uac-close { color: white; background: transparent; border: none; border-radius: 0; padding: 6px 14px; margin: 0; box-shadow: none; transition: none; }
                .uac-close:hover { background-color: #e81123; transition: none; }
                .uac-content { background-color: #ffffff; border-bottom: 1px solid #dfdfdf; }
                .uac-entry { border: 1px solid #0078d7; padding: 6px; border-radius: 0; background-color: #ffffff; color: #000000; }
                .uac-btn-box { background-color: #f0f0f0; }
                .uac-btn { background-image: none; background-color: #e1e1e1; border: 1px solid #adadad; border-radius: 0; padding: 14px 0; font-size: 12px; color: #000000; box-shadow: none; }
                .uac-btn:hover { background-color: #e5f1fb; border: 1px solid #0078d7; }
                .uac-sep { background-color: #adadad; min-width: 1px; }
            """
            css.load_from_data(css_data.encode('utf-8'))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            self.pw.grab_focus()

        def on_drag(self, widget, event):
            if event.button == 1:
                self.begin_move_drag(event.button, event.x_root, event.y_root, event.time)
                return True
            return False

        def on_key(self, w, event):
            if event.keyval == Gdk.KEY_Escape:
                os._exit(1)
                return True
            return False

        def confirm(self):
            pw = self.pw.get_text()
            if not pw:
                return
            sys.stdout.write(pw + "\n")
            sys.stdout.flush()
            os._exit(0)

    win = UAC()
    win.show_all()
    win.pw.grab_focus()
    play_uac_sound()
    Gtk.main()

if __name__ == "__main__":
    if is_askpass_mode():
        askpass()
    elif len(sys.argv) > 1:
        launch()
    else:
        prompt_and_launch()