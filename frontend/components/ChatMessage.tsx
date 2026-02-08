'use client';

import { ChatMessage as Message } from '@/types/chat';
import { TransactionCard } from './TransactionCard';
import { motion } from 'framer-motion';
import { Bot, User } from 'lucide-react';
import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessageProps {
    message: Message;
}

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
    const isUser = message.role === 'user';

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'} group`}
        >
            {/* Avatar */}
            <div className="flex-shrink-0">
                <div className={`
                    w-10 h-10 rounded-2xl flex items-center justify-center
                    ${isUser
                        ? 'bg-gradient-to-br from-purple-500 to-pink-600 shadow-lg shadow-purple-500/50'
                        : 'bg-gradient-to-br from-tron-500 via-blue-500 to-cyan-500 shadow-lg shadow-tron-500/50'
                    }
                    group-hover:scale-110 transition-transform duration-300
                `}>
                    {isUser ? (
                        <User className="w-5 h-5 text-white" />
                    ) : (
                        <Bot className="w-5 h-5 text-white" />
                    )}
                </div>
            </div>

            {/* Message Content */}
            <div className={`flex-1 max-w-3xl ${isUser ? 'text-right' : 'text-left'}`}>
                <div className={`
                    inline-block p-4 rounded-2xl
                    ${isUser
                        ? 'bg-gradient-to-br from-purple-500/20 to-pink-600/20 backdrop-blur-xl border border-purple-500/30'
                        : 'glass-tron'
                    }
                    group-hover:shadow-xl transition-all duration-300
                `}>
                    {/* Text Content with Markdown Rendering */}
                    <div className="text-gray-100 prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                                // Customize heading styles
                                h1: ({ node, ...props }) => <h1 className="text-2xl font-bold text-white mb-3 mt-4 first:mt-0" {...props} />,
                                h2: ({ node, ...props }) => <h2 className="text-xl font-bold text-white mb-2 mt-4 first:mt-0" {...props} />,
                                h3: ({ node, ...props }) => <h3 className="text-lg font-bold text-white mb-2 mt-3 first:mt-0" {...props} />,
                                // Customize list styles
                                ul: ({ node, ...props }) => <ul className="list-disc list-inside space-y-1 my-2" {...props} />,
                                ol: ({ node, ...props }) => <ol className="list-decimal list-inside space-y-1 my-2" {...props} />,
                                li: ({ node, ...props }) => <li className="text-gray-100" {...props} />,
                                // Customize code blocks
                                code: ({ node, inline, ...props }: any) =>
                                    inline ? (
                                        <code className="px-2 py-0.5 rounded bg-black/30 text-tron-400 font-mono text-sm" {...props} />
                                    ) : (
                                        <code className="block px-4 py-2 rounded-lg bg-black/40 text-tron-400 font-mono text-sm my-2 overflow-x-auto" {...props} />
                                    ),
                                // Customize links
                                a: ({ node, ...props }) => (
                                    <a
                                        className="text-tron-400 hover:text-tron-300 underline"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        {...props}
                                    />
                                ),
                                // Customize paragraphs
                                p: ({ node, ...props }) => <p className="mb-2 last:mb-0 text-gray-100" {...props} />,
                                // Customize strong/bold
                                strong: ({ node, ...props }) => <strong className="font-bold text-white" {...props} />,
                                // Customize emphasis/italic
                                em: ({ node, ...props }) => <em className="italic text-gray-200" {...props} />,
                                // Customize blockquotes
                                blockquote: ({ node, ...props }) => (
                                    <blockquote className="border-l-4 border-tron-500 pl-4 italic text-gray-300 my-2" {...props} />
                                ),
                            }}
                        >
                            {message.content}
                        </ReactMarkdown>
                    </div>

                    {/* Transaction Cards List */}
                    {message.transactions && message.transactions.length > 0 && (
                        <div className="mt-4 space-y-4">
                            {message.transactions.map((tx, idx) => (
                                <TransactionCard key={idx} transaction={tx} />
                            ))}
                        </div>
                    )}
                </div>

                {/* Timestamp */}
                <div className={`text-xs text-gray-500 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
                    {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
                        hour: '2-digit',
                        minute: '2-digit',
                    })}
                </div>
            </div>
        </motion.div>
    );
});
