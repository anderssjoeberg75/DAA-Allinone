import React, { useEffect, useRef, useState, memo, useCallback } from 'react';
import { Send, Image as ImageIcon, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

// Memoized message component
const MessageItem = memo(({ m }) => (
  <div className={`msg-container ${m.role === 'user' ? 'user' : 'ai'}`}>
    <div className={`msg-label ${m.role === 'user' ? 'user' : 'ai'}`}>
      {m.role === 'user' ? 'YOU' : 'DAA'}
    </div>
    <div className={`message-bubble ${m.role === 'user' ? 'msg-user' : 'msg-ai'}`}>
      {m.role === 'user' ? (
        <>
          {m.image && (
            <img src={m.image} alt="User Upload" style={{ maxWidth: '200px', borderRadius: '4px', marginBottom: '5px', display: 'block' }} />
          )}
          {m.text}
        </>
      ) : (
        <div className="markdown-body">
          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{m.text}</ReactMarkdown>
        </div>
      )}
    </div>
  </div>
));

const ChatPanel = ({ messages, onSendMessage }) => {
  const [input, setInput] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [attachedImage, setAttachedImage] = useState(null); // base64 string
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() && !attachedImage) return;

    // Pass object if image exists, otherwise string
    if (attachedImage) {
      onSendMessage({ text: input, image: attachedImage });
    } else {
      onSendMessage(input);
    }

    setInput("");
    setAttachedImage(null);
  };

  // --- Drag and Drop Handlers ---
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const imgBase64 = e.target.result;
          setAttachedImage(imgBase64);
          // Auto-send immediately
          onSendMessage({ text: "", image: imgBase64 });
          setAttachedImage(null);
        };
        reader.readAsDataURL(file);
      }
    }
  }, [onSendMessage]);

  // Handle Paste (Ctrl+V)
  const handlePaste = useCallback((e) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      const file = e.clipboardData.files[0];
      if (file.type.startsWith('image/')) {
        e.preventDefault();
        const reader = new FileReader();
        reader.onload = (evt) => {
          const imgBase64 = evt.target.result;
          setAttachedImage(imgBase64);
          // Auto-send immediately
          onSendMessage({ text: "", image: imgBase64 });
          setAttachedImage(null);
        };
        reader.readAsDataURL(file);
      }
    }
  }, [onSendMessage]);


  return (
    <div
      className="chat-window-wrapper"
      style={{ display: 'flex', flexDirection: 'column', flex: 1, position: 'relative', overflow: 'hidden' }}
      onDragEnter={handleDrag}
    >
      {/* Drag Overlay */}
      {dragActive && (
        <div
          className="drag-overlay"
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.7)', zIndex: 100,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '18px', border: '2px dashed #58a6ff'
          }}
        >
          Drop image to analyze
        </div>
      )}

      <div className="chat-window" style={{ flex: 1, overflowY: 'auto' }}>
        {messages.map((m, i) => (
          <MessageItem key={i} m={m} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Image Preview Container */}
      {attachedImage && (
        <div style={{ padding: '5px 10px', background: '#0d1117', borderTop: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative' }}>
            <img src={attachedImage} alt="Preview" style={{ height: '60px', borderRadius: '4px', border: '1px solid #30363d' }} />
            <button
              onClick={() => setAttachedImage(null)}
              style={{
                position: 'absolute', top: '-5px', right: '-5px',
                background: '#ff4444', color: 'white', border: 'none',
                borderRadius: '50%', width: '16px', height: '16px',
                display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer'
              }}
            >
              <X size={10} />
            </button>
          </div>
          <span style={{ fontSize: '12px', color: '#8b949e' }}>Image attached</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="chat-input-form" style={{ paddingTop: '10px' }}>
        <input
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Type command or drop image..."
          onPaste={handlePaste}
        />
        <button type="submit" className="btn-icon">
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};

export default ChatPanel;