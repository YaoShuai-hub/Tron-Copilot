'use client';

import { WalletButton } from './WalletButton';
import { useWallet } from '@tronweb3/tronwallet-adapter-react-hooks';
import { useNetwork } from '@/contexts/NetworkContext';
import { useChatStore } from '@/lib/store';
import { useEffect } from 'react';
import { Sparkles, Wifi } from 'lucide-react';

function NetworkBadge() {
    const { network, config, isDetecting } = useNetwork();
    const { connected } = useWallet();

    if (!connected) return null;

    return (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass border border-white/10">
            <Wifi className={`w-4 h-4 ${isDetecting ? 'animate-pulse' : ''}`} />
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${config.color}`} />
                <span className="text-sm font-medium text-white">
                    {config.displayName}
                </span>
            </div>
        </div>
    );
}

export function Header() {
    const { address } = useWallet();
    const setWalletAddress = useChatStore((state) => state.setWalletAddress);

    useEffect(() => {
        setWalletAddress(address || null);
    }, [address, setWalletAddress]);

    return (
        <header className="relative z-50 glass border-b border-white/10 px-6 py-4 backdrop-blur-xl">
            {/* Animated gradient background */}
            <div className="absolute inset-0 bg-gradient-to-r from-tron-500/10 via-purple-500/5 to-tron-500/10 animate-gradient" />

            <div className="relative max-w-7xl mx-auto flex items-center justify-between">
                {/* Logo */}
                <div className="flex items-center gap-3 group">
                    <div className="relative">
                        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-tron-500 via-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-tron-500/50 group-hover:shadow-tron-500/80 transition-all duration-300 group-hover:scale-110">
                            <Sparkles className="w-6 h-6 text-white animate-pulse" />
                        </div>
                        <div className="absolute inset-0 rounded-2xl bg-tron-500 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold bg-gradient-to-r from-white via-blue-100 to-white bg-clip-text text-transparent">
                            TRON Copilot
                        </h1>
                        <p className="text-xs text-gray-400 flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                            AI-Powered Asset Manager
                        </p>
                    </div>
                </div>

                {/* Network Badge */}
                <NetworkBadge />

                {/* Wallet Button */}
                <WalletButton />
            </div>
        </header>
    );
}
