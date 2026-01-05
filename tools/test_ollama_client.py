import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from aura_nexus_app import OllamaClient, Message

print('Testing OllamaClient...')
client = OllamaClient()
print('base_url', client.base_url)
print('default model', client.model)
print('Chat default:', repr(client.chat([Message('user','Say hi')], 'System prompt')))

print('\nTesting explicit model: lexi-uncensored')
print('Chat lexi:', repr(client.chat([Message('user','Say hi')], None, None, model='lexi-uncensored')))

print('\nTesting wrong server error...')
client_bad = OllamaClient(base_url='http://localhost:11435')
print('Chat wrong url:', repr(client_bad.chat([Message('user','Say hi')], 'System prompt')))
