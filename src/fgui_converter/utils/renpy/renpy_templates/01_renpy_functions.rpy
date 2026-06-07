init python:
    def check_input_length(input_value_object):
        str_length = len(input_value_object.get_text())
        current, editable = renpy.get_editable_input_value()
        return (not editable or current!=input_value_object) and str_length == 0
