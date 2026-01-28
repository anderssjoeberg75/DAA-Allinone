import React, { useEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';

const ChatPanel = ({ messages, onSendMessage }) => {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSendMessage(input);
    setInput("");
  };

  return (
    <>
      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth:'85%' }}>
            <div className="msg-label" style={{ color: m.role==='user'?'#00ffcc':'#58a6ff', textAlign: m.role==='user'?'right':'left' }}>
              {m.role === 'user' ? 'YOU' : 'DAA'}
            </div>
            <div className={`message-bubble ${m.role === 'user' ? 'msg-user' : 'msg-ai'}`}>
              {m.text}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef}/>
      </div>
      
      <form onSubmit={handleSubmit} className="chat-input-form">
        <input 
          className="chat-input"
          value={input} 
          onChange={e => setInput(e.target.value)} 
          placeholder="Type command..." 
        />
        <button type="submit" className="btn-icon">
          <Send size={18} />
        </button>
      </form>
    </>
  );
};

export default ChatPanel;