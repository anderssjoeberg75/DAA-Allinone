import { useRef, useCallback } from 'react';

export const useAudioQueue = () => {
    const audioQueue = useRef([]);
    const isPlaying = useRef(false);
    const textBuffer = useRef("");
    const ttsInProgress = useRef(false);
    const processingTimeout = useRef(null);

    // Play next audio chunk from queue
    const playNextInQueue = useCallback(async () => {
        if (isPlaying.current || audioQueue.current.length === 0) return;

        isPlaying.current = true;
        const audioBlob = audioQueue.current.shift();
        const url = URL.createObjectURL(audioBlob);
        const audio = new Audio(url);

        const cleanup = () => {
            URL.revokeObjectURL(url);
            isPlaying.current = false;
            playNextInQueue();
        };

        audio.onended = cleanup;
        audio.onerror = cleanup;

        try {
            await audio.play();
        } catch (e) {
            console.warn("Audio playback error:", e);
            cleanup();
        }
    }, []);

    // Add audio blob to queue
    const addToQueue = useCallback((blob) => {
        audioQueue.current.push(blob);
        playNextInQueue();
    }, [playNextInQueue]);

    // Generate TTS for a text chunk
    const generateTTSChunk = useCallback(async (text, isMuted) => {
        if (isMuted || !text || text.trim().length === 0) return;

        // Use standard environment variable or default
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

        try {
            const response = await fetch(`${apiUrl}/api/tts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text.trim() })
            });

            if (response.ok) {
                const blob = await response.blob();
                addToQueue(blob);
            }
        } catch (e) {
            console.warn("TTS generation failed:", e);
        }
    }, [addToQueue]);

    // Process text buffer and generate TTS for complete sentences
    const processTextBuffer = useCallback(async (isMuted) => {
        if (ttsInProgress.current || isMuted) return;

        const text = textBuffer.current;
        if (!text || text.length === 0) return;

        // Look for complete sentences
        const sentenceMatch = text.match(/^(.+?[.!?]\s*)/);

        if (sentenceMatch) {
            const sentence = sentenceMatch[1];
            textBuffer.current = text.slice(sentence.length);
            ttsInProgress.current = true;
            await generateTTSChunk(sentence, isMuted);
            ttsInProgress.current = false;

            if (textBuffer.current.length > 0) {
                setTimeout(() => processTextBuffer(isMuted), 0);
            }
        } else if (text.length > 150) {
            const chunk = text.slice(0, 150);
            textBuffer.current = text.slice(150);
            ttsInProgress.current = true;
            await generateTTSChunk(chunk, isMuted);
            ttsInProgress.current = false;

            if (textBuffer.current.length > 0) {
                setTimeout(() => processTextBuffer(isMuted), 0);
            }
        }
    }, [generateTTSChunk]);

    // Add text to buffer
    const addTextToBuffer = useCallback((text, isMuted) => {
        if (!text) return;
        textBuffer.current += text;

        if (processingTimeout.current) clearTimeout(processingTimeout.current);
        processingTimeout.current = setTimeout(() => {
            processTextBuffer(isMuted);
        }, 50);
    }, [processTextBuffer]);

    // Clear all audio
    const clearAudio = useCallback(() => {
        window.speechSynthesis.cancel();
        audioQueue.current = [];
        textBuffer.current = "";
        isPlaying.current = false;
        ttsInProgress.current = false;
        if (processingTimeout.current) {
            clearTimeout(processingTimeout.current);
            processingTimeout.current = null;
        }
    }, []);

    // Filter text for TTS - removes system messages
    const filterTextForTTS = (text) => {
        if (!text) return "";
        let filtered = text;
        filtered = filtered.replace(/\[System:.*?\]/gi, "");
        filtered = filtered.replace(/^(IMPORTANT:|CRITICAL:|NOTE:|WARNING:).*$/gim, "");
        filtered = filtered.replace(/^-{3,}.*$/gm, "");
        filtered = filtered.replace(/---\s*REAL-TIME INFORMATION.*?---/gs, "");
        filtered = filtered.replace(/\n{3,}/g, "\n\n").trim();
        return filtered;
    };

    return {
        addToQueue,
        addTextToBuffer,
        clearAudio,
        filterTextForTTS
    };
};
