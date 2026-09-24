# PyInstaller runtime hook to fix nagisa's implicit relative imports
# (nagisa/train.py executes `import prepro`, `import model`, etc. which fail when frozen in PyInstaller)
import sys

try:
    import nagisa.prepro
    import nagisa.model
    import nagisa.mecab_system_eval
    import nagisa.tagger
    sys.modules['prepro'] = nagisa.prepro
    sys.modules['model'] = nagisa.model
    sys.modules['mecab_system_eval'] = nagisa.mecab_system_eval
    sys.modules['tagger'] = nagisa.tagger
except Exception:
    pass
