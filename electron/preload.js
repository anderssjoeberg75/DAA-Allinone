const { contextBridge, ipcRenderer } = require('electron');

// Vi exponerar en säker API-brygga till Frontend (React)
// Detta gör att vi kan slå på 'contextIsolation: true' i main.js för maximal säkerhet.

contextBridge.exposeInMainWorld('electronAPI', {
    // Funktion för att skicka meddelanden TILL Main-processen (t.ex. "stäng appen")
    send: (channel, data) => {
        // En enkel whitelist kan läggas till här för extra säkerhet
        // t.ex: const validChannels = ['app:quit', 'app:minimize'];
        // if (validChannels.includes(channel)) ipcRenderer.send(channel, data);
        ipcRenderer.send(channel, data);
    },
    
    // Funktion för att lyssna på meddelanden FRÅN Main-processen
    on: (channel, func) => {
        const subscription = (event, ...args) => func(...args);
        ipcRenderer.on(channel, subscription);

        // Returnera en funktion för att ta bort lyssnaren (viktigt för React useEffect)
        return () => {
            ipcRenderer.removeListener(channel, subscription);
        };
    }
});