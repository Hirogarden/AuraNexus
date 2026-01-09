const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  sendMessage: (message) => ipcRenderer.invoke('send-message', message),
  onAgentResponse: (callback) => ipcRenderer.on('agent-response', callback)
});
