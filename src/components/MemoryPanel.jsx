import React, { useState, useEffect } from 'react';
import { Search, Plus, Trash2, Save, X, Activity } from 'lucide-react'; // Swapped Brain for Activity just in case

const MemoryPanel = () => {
    const [memories, setMemories] = useState([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [newMemory, setNewMemory] = useState("");
    const [isAdding, setIsAdding] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Styles object to guarantee visibility
    const styles = {
        container: {
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
            color: '#e0e6ed',
            fontFamily: 'Segoe UI, sans-serif'
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '15px',
            borderBottom: '1px solid #30363d',
            paddingBottom: '10px'
        },
        title: {
            margin: 0,
            color: '#A78BFA',
            fontSize: '18px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
        },
        searchContainer: {
            position: 'relative',
            marginBottom: '15px'
        },
        input: {
            width: '100%',
            background: '#0d1117',
            border: '1px solid #30363d',
            color: '#e0e6ed',
            padding: '8px 10px 8px 35px',
            borderRadius: '4px',
            boxSizing: 'border-box',
            fontSize: '14px'
        },
        list: {
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
        },
        item: {
            background: '#161b22',
            border: '1px solid #30363d',
            padding: '12px',
            borderRadius: '6px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start'
        },
        button: {
            background: '#238636',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px'
        }
    };

    const fetchMemories = async () => {
        setLoading(true);
        setError(null);
        try {
            const url = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const endpoint = searchQuery.trim()
                ? `${url}/api/memories/search`
                : `${url}/api/memories`;

            const method = searchQuery.trim() ? 'POST' : 'GET';
            const body = searchQuery.trim() ? JSON.stringify({ query: searchQuery, limit: 50 }) : null;

            console.log('Fetching memories from:', endpoint); // DEBUG Log

            const res = await fetch(endpoint, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body
            });

            if (!res.ok) {
                throw new Error(`Server returned ${res.status}`);
            }

            const data = await res.json();
            if (data.error) throw new Error(data.error);

            setMemories(data.results || []);
        } catch (e) {
            console.error("Memory fetch error:", e);
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const timer = setTimeout(fetchMemories, 500);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const handleDelete = async (id) => {
        if (!confirm("Delete this memory?")) return;
        try {
            const url = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            await fetch(`${url}/api/memories/${id}`, { method: 'DELETE' });
            setMemories(prev => prev.filter(m => m.id !== id));
        } catch (e) {
            alert("Delete failed: " + e.message);
        }
    };

    const handleAdd = async () => {
        if (!newMemory.trim()) return;
        try {
            const url = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            await fetch(`${url}/api/memories/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: newMemory })
            });
            setNewMemory("");
            setIsAdding(false);
            fetchMemories();
        } catch (e) {
            alert("Add failed: " + e.message);
        }
    };

    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h3 style={styles.title}>
                    <Activity size={20} /> Memory Explorer
                </h3>
                <button
                    onClick={() => setIsAdding(!isAdding)}
                    style={{ ...styles.button, background: isAdding ? '#ff4444' : '#A78BFA', width: '30px', height: '30px', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    title="Add Memory"
                >
                    {isAdding ? <X size={18} /> : <Plus size={18} />}
                </button>
            </div>

            <div style={styles.searchContainer}>
                <Search size={16} style={{ position: 'absolute', left: '10px', top: '10px', color: '#8b949e' }} />
                <input
                    type="text"
                    placeholder="Search memories..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={styles.input}
                />
            </div>

            {isAdding && (
                <div style={{ marginBottom: '15px', background: '#161b22', padding: '10px', borderRadius: '6px', border: '1px solid #30363d' }}>
                    <textarea
                        value={newMemory}
                        onChange={(e) => setNewMemory(e.target.value)}
                        style={{ ...styles.input, minHeight: '60px', marginBottom: '10px', padding: '8px' }}
                        placeholder="Type memory here..."
                    />
                    <button onClick={handleAdd} style={styles.button}><Save size={14} style={{ marginRight: '5px' }} /> Save</button>
                </div>
            )}

            <div style={styles.list}>
                {loading && <div style={{ textAlign: 'center', color: '#8b949e' }}>Loading...</div>}
                {error && <div style={{ color: '#ff4444', textAlign: 'center' }}>Error: {error} (Did you restart backend?)</div>}

                {!loading && !error && memories.length === 0 && (
                    <div style={{ textAlign: 'center', color: '#8b949e' }}>No memories found.</div>
                )}

                {memories.map((mem) => (
                    <div key={mem.id} style={styles.item}>
                        <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '14px', color: '#e0e6ed', whiteSpace: 'pre-wrap' }}>{mem.memory}</div>
                            <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '5px' }}>
                                {mem.created_at ? new Date(mem.created_at).toLocaleDateString() : 'Unknown Date'}
                            </div>
                        </div>
                        <button
                            onClick={() => handleDelete(mem.id)}
                            style={{ background: 'transparent', border: 'none', color: '#6e7681', cursor: 'pointer' }}
                        >
                            <Trash2 size={16} />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default MemoryPanel;
