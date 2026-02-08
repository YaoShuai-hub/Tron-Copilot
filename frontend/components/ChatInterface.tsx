'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useChatStore } from '@/lib/store';
import { ChatMessage } from './ChatMessage';
import { Virtuoso } from 'react-virtuoso';
import { Send, Loader2 } from 'lucide-react';
import { StreamParser } from '@/lib/stream-parser';
import { nanoid } from '@/lib/nanoid';
import { motion } from 'framer-motion';
import { useNetwork } from '@/contexts/NetworkContext';

export function ChatInterface() {
    const messages = useChatStore((state) => state.messages);
    const isStreaming = useChatStore((state) => state.isStreaming);
    const addMessage = useChatStore((state) => state.addMessage);
    const updateMessage = useChatStore((state) => state.updateMessage);
    const setStreaming = useChatStore((state) => state.setStreaming);
    const walletAddress = useChatStore((state) => state.walletAddress);
    const { network } = useNetwork(); // Get detected network

    const [input, setInput] = useState('');
    const [toolCards, setToolCards] = useState<Array<{ name: string; description: string }>>([]);
    const virtuosoRef = useRef<any>(null);
    const parserRef = useRef(new StreamParser());

    // Auto-scroll to bottom
    const followOutput = useRef(true);

    useEffect(() => {
        if (messages.length > 0 && followOutput.current) {
            virtuosoRef.current?.scrollToIndex({
                index: messages.length - 1,
                behavior: 'smooth',
            });
        }
    }, [messages.length]);

    useEffect(() => {
        let active = true;
        const loadTools = async () => {
            try {
                const resp = await fetch('/api/tools');
                if (!resp.ok) return;
                const data = await resp.json();
                if (active && Array.isArray(data.tools)) {
                    setToolCards(data.tools);
                }
            } catch {
                // ignore tool list load failures
            }
        };
        loadTools();
        return () => {
            active = false;
        };
    }, []);

    const handleSend = useCallback(async () => {
        if (!input.trim() || isStreaming) return;

        const userMessage = {
            id: nanoid(),
            role: 'user' as const,
            content: input.trim(),
            timestamp: new Date(),
        };

        addMessage(userMessage);
        setInput('');
        setStreaming(true);

        // Create assistant message
        const assistantMessageId = nanoid();
        addMessage({
            id: assistantMessageId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
        });

        try {
            // Call API route
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: input.trim(),
                    walletAddress: walletAddress,
                    network: network, // Pass detected network to backend
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to fetch');
            }

            parserRef.current.reset();
            let accumulatedText = '';

            const fullText = await response.text();
            const parsed = parserRef.current.parse(fullText);
            const remaining = parserRef.current.flush();

            for (const item of [...parsed, ...remaining]) {
                if (item.type === 'text') {
                    accumulatedText += item.content;
                    updateMessage(assistantMessageId, accumulatedText);
                } else if (item.type === 'transaction') {
                    const currentMessages = useChatStore.getState().messages;
                    const messageToUpdate = currentMessages.find(m => m.id === assistantMessageId);
                    if (messageToUpdate) {
                        useChatStore.setState({
                            messages: currentMessages.map(m =>
                                m.id === assistantMessageId
                                    ? {
                                        ...m,
                                        transactions: [...(m.transactions || []), item.transaction]
                                    }
                                    : m
                            ),
                        });
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            updateMessage(assistantMessageId, '抱歉，发生了错误。请稍后重试。');
        } finally {
            setStreaming(false);
        }
    }, [input, isStreaming, walletAddress, addMessage, updateMessage, setStreaming]);

    const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }, [handleSend]);

    return (
        <div className="flex flex-col h-full">
            {/* Chat Messages */}
            <div className="flex-1 overflow-hidden">
                {messages.length === 0 ? (
                    <EmptyState setInput={setInput} tools={toolCards} />
                ) : (
                    <Virtuoso
                        ref={virtuosoRef}
                        data={messages}
                        itemContent={(index, message) => (
                            <div className="px-6 py-2">
                                <ChatMessage key={message.id} message={message} />
                            </div>
                        )}
                        followOutput={followOutput.current}
                        atBottomStateChange={(atBottom) => {
                            followOutput.current = atBottom;
                        }}
                    />
                )}
            </div>

            {/* Input Area */}
            <div className="border-t border-white/10 bg-black/20 backdrop-blur-xl p-6">
                <div className="max-w-4xl mx-auto">
                    <div className="relative">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder={
                                walletAddress
                                    ? "输入消息... (Shift+Enter 换行，Enter 发送)"
                                    : "请先连接钱包..."
                            }
                            disabled={!walletAddress || isStreaming}
                            className="w-full px-4 py-3 pr-12 rounded-2xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-tron-500 focus:border-transparent resize-none disabled:opacity-50 disabled:cursor-not-allowed"
                            rows={1}
                            style={{ minHeight: '48px', maxHeight: '200px' }}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || !walletAddress || isStreaming}
                            className="absolute right-2 bottom-2 p-2 rounded-xl bg-gradient-to-r from-tron-500 to-tron-600 hover:from-tron-600 hover:to-tron-700 text-white transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105"
                        >
                            {isStreaming ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Send className="w-5 h-5" />
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}


function EmptyState({
    setInput,
    tools,
}: {
    setInput: (value: string) => void;
    tools: Array<{ name: string; description: string }>;
}) {
    return (
        <div className="flex items-center justify-center h-full relative">
            {/* Radial gradient background */}
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-96 h-96 bg-gradient-to-br from-tron-500/20 via-purple-500/10 to-transparent rounded-full blur-3xl animate-pulse" />
            </div>

            <div className="relative text-center space-y-6 max-w-2xl px-6">
                {/* Animated Icon */}
                <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ duration: 0.8, type: "spring" }}
                    className="relative mx-auto w-24 h-24"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-tron-500 via-blue-500 to-purple-600 rounded-3xl blur-2xl opacity-60 animate-pulse" />
                    <div className="relative w-24 h-24 rounded-3xl bg-gradient-to-br from-tron-500 via-blue-500 to-purple-600 flex items-center justify-center shadow-2xl">
                        <svg className="w-12 h-12 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                        </svg>
                    </div>
                </motion.div>

                {/* Title */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <h2 className="text-3xl font-bold bg-gradient-to-r from-white via-blue-100 to-white bg-clip-text text-transparent mb-2">
                        TRON Asset Management Copilot
                    </h2>
                    <p className="text-gray-400">
                        您的AI助手已准备就绪 <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse mx-1" />
                    </p>
                    <p className="text-gray-500 text-sm mt-2">
                        连接钱包后即可开始智能对话
                    </p>
                </motion.div>

                {/* Tool Cards */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                    className="grid grid-cols-2 gap-3 mt-8 max-h-64 overflow-y-auto pr-1"
                >
                    {tools.length > 0 ? (
                        tools.map((tool, idx) => (
                            <ToolCard
                                key={tool.name}
                                name={tool.name}
                                description={tool.description}
                                delay={0.4 + idx * 0.02}
                                setInput={setInput}
                            />
                        ))
                    ) : (
                        <>
                            <ExamplePrompt icon="💰" text="查询钱包余额" delay={0.5} setInput={setInput} />
                            <ExamplePrompt icon="💸" text="转账资产" delay={0.6} setInput={setInput} />
                            <ExamplePrompt icon="⚡" text="优化能量费用" delay={0.7} setInput={setInput} />
                            <ExamplePrompt icon="🛡️" text="安全检查" delay={0.8} setInput={setInput} />
                        </>
                    )}
                </motion.div>

                {/* Hint */}
                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1 }}
                    className="text-xs text-gray-600 mt-4"
                >
                    提示：连接钱包后即可体验完整功能
                </motion.p>
            </div>
        </div>
    );
}

function ExamplePrompt({ icon, text, delay, setInput }: { icon: string; text: string; delay: number; setInput: (value: string) => void }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay }}
            whileHover={{ scale: 1.05, y: -2 }}
            onClick={() => setInput(text)}
            className="group relative px-4 py-3 rounded-xl glass border-white/10 text-sm text-gray-300 hover:border-tron-500/50 hover:bg-tron-500/10 transition-all cursor-pointer overflow-hidden"
        >
            <div className="relative flex items-center gap-2">
                <span className="text-lg">{icon}</span>
                <span className="font-medium">{text}</span>
            </div>
            <div className="absolute inset-0 bg-gradient-to-r from-tron-500/0 via-tron-500/10 to-tron-500/0 opacity-0 group-hover:opacity-100 transition-opacity" />
        </motion.div>
    );
}

function ToolCard({
    name,
    description,
    delay,
    setInput,
}: {
    name: string;
    description: string;
    delay: number;
    setInput: (value: string) => void;
}) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay }}
            whileHover={{ scale: 1.03, y: -2 }}
            onClick={() => setInput(name)}
            className="group relative px-4 py-3 rounded-xl glass border-white/10 text-sm text-gray-300 hover:border-tron-500/50 hover:bg-tron-500/10 transition-all cursor-pointer overflow-hidden text-left"
        >
            <div className="relative flex flex-col gap-1">
                <span className="font-medium text-tron-300">{name}</span>
                <span className="text-xs text-gray-400 line-clamp-2">{description}</span>
            </div>
            <div className="absolute inset-0 bg-gradient-to-r from-tron-500/0 via-tron-500/10 to-tron-500/0 opacity-0 group-hover:opacity-100 transition-opacity" />
        </motion.div>
    );
}
