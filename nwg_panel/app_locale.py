import locale,gettext,os

def lang_init():
    """
    Initialize a translation framework (gettext).
    Typical use::
        _ = lang_init()

    :return: A string translation function.
    :rtype: (str) -> str
    """
    _locale, _encoding = locale.getdefaultlocale()  # Default system values

    dir_name = os.path.dirname(__file__)
    path = os.path.join(dir_name,'locale')

    lang = gettext.translation('nwg-panel', path, [_locale])
    return lang.gettext

