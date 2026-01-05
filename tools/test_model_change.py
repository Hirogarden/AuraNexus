import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from aura_nexus_app import AuraNexusWindow, Message, OllamaClient
from PySide6.QtWidgets import QApplication

# Instantiate a minimal GUI window; avoid showing
app = QApplication([])
win = AuraNexusWindow()
print('initial model:', win.ollama.model)
# Add a new model to the combobox and set it
win.model_combo.addItem('lexi-uncensored')
win.model_combo.setCurrentText('lexi-uncensored')
# Fire the on_change handler
win._on_model_combo_changed()
print('after change model:', win.ollama.model)
# Invoke _llm_chat to ensure it uses the new model
res = win._llm_chat([Message('user', 'Say hi')], win._effective_system_prompt(), {})
print('chat result:', res)
# Try a direct OllamaClient call with explicit model param
oc = OllamaClient()
print('explicit model chat:', oc.chat([Message('user', 'Say hi')], None, None, model='lexi-uncensored'))
