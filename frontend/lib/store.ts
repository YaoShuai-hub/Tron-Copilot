import { create } from 'zustand';
import { ChatMessage } from '@/types/chat';

interface ChatStore {
    messages: ChatMessage[];
    isStreaming: boolean;
    walletAddress: string | null;

    addMessage: (message: ChatMessage) => void;
    updateMessage: (id: string, content: string) => void;
    setStreaming: (streaming: boolean) => void;
    setWalletAddress: (address: string | null) => void;
    clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
    messages: [],
    isStreaming: false,
    walletAddress: null,

    addMessage: (message) =>
        set((state) => ({
            messages: [...state.messages, message],
        })),

    updateMessage: (id, content) =>
        set((state) => ({
            messages: state.messages.map((msg) =>
                msg.id === id ? { ...msg, content } : msg
            ),
        })),

    setStreaming: (streaming) => set({ isStreaming: streaming }),

    setWalletAddress: (address) => set({ walletAddress: address }),

    clearMessages: () => set({ messages: [] }),
}));
