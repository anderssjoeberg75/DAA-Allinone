import { useEffect, useState, useRef } from 'react';
import io from 'socket.io-client';

export const useSocket = (url) => {
    const [socket, setSocket] = useState(null);
    const [isConnected, setIsConnected] = useState(false);

    // Use ref to keep socket instance stable across renders
    const socketRef = useRef(null);

    useEffect(() => {
        // Use environment variable or default
        const apiUrl = url || import.meta.env.VITE_API_URL || 'http://localhost:8000';

        if (!socketRef.current) {
            socketRef.current = io(apiUrl, {
                reconnection: true,
                reconnectionAttempts: 10,
                reconnectionDelay: 2000,
                transports: ['websocket', 'polling']
            });

            const s = socketRef.current;
            setSocket(s);

            s.on('connect', () => setIsConnected(true));
            s.on('disconnect', () => setIsConnected(false));
        }

        return () => {
            if (socketRef.current) {
                socketRef.current.disconnect();
                socketRef.current = null;
            }
        };
    }, [url]);

    return { socket, isConnected };
};
