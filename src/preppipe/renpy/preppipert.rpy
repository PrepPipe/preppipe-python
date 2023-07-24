# This is the runtime library for Ren'Py engine.

init offset = -1

screen preppipe_error_screen(who, what):
  modal False
  zorder 1
  window id "window":
    xpos 0.6
    ypos 0.2
    text what id "what"


init offset = 0

define preppipe_error_sayer = Character("PrepPipe Error", who_color="#ff0000", what_color="#ff0000", interact=False, mode="screen", screen="preppipe_error_screen")
define preppipe_error_sayer_en = preppipe_error_sayer
define preppipe_error_sayer_zh_cn = Character("语涵编译器错误", kind=preppipe_error_sayer)
define preppipe_error_sayer_zh_hk = Character("語涵編譯器錯誤", kind=preppipe_error_sayer)

label __preppipe_ending__(ending_name=''):
  $ MainMenu(confirm=False)