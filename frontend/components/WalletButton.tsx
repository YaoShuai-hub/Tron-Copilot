'use client';

import { useWallet } from '@tronweb3/tronwallet-adapter-react-hooks';
import { useState, useRef, useEffect } from 'react';
import { Wallet, Copy, LogOut, RefreshCw, Check } from 'lucide-react';

export function WalletButton() {
    const { address, connected, select, disconnect, wallet } = useWallet();
    const [isOpen, setIsOpen] = useState(false);
    const [copied, setCopied] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        // Use click instead of mousedown to avoid potential conflicts
        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, []);

    const handleCopy = async () => {
        if (address) {
            try {
                await navigator.clipboard.writeText(address);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
            }
        }
    };

    const handleChangeWallet = () => {
        disconnect();
        setIsOpen(false);
    };

    const handleDisconnect = () => {
        disconnect();
        setIsOpen(false);
    };

    const formatAddress = (addr: string) => {
        return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
    };

    if (!connected || !address) {
        return (
            <button
                onClick={() => select('TronLink' as any)}
                className="group relative px-6 py-2.5 rounded-xl bg-gradient-to-r from-tron-500 to-tron-600 hover:from-tron-600 hover:to-tron-700 text-white font-medium transition-all duration-300 hover:scale-105 hover:shadow-lg hover:shadow-tron-500/50"
            >
                <div className="flex items-center gap-2">
                    <Wallet className="w-5 h-5" />
                    <span>Connect Wallet</span>
                </div>
                <div className="absolute inset-0 rounded-xl bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity blur-xl" />
            </button>
        );
    }

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="group relative px-4 py-2.5 rounded-xl glass border-tron-500/50 hover:border-tron-500 transition-all duration-300 hover:bg-white/10"
            >
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-tron-500 to-tron-700 flex items-center justify-center">
                        <Wallet className="w-4 h-4 text-white" />
                    </div>
                    <div className="text-left">
                        <div className="text-sm font-mono text-white">
                            {formatAddress(address)}
                        </div>
                        <div className="text-xs text-gray-400">
                            {wallet?.adapter.name || 'Connected'}
                        </div>
                    </div>
                </div>
            </button>

            {isOpen && (
                <div
                    className="absolute right-0 mt-2 w-56 rounded-xl glass border border-white/10 shadow-2xl overflow-hidden z-[9999]"
                    style={{ backgroundColor: 'rgba(20, 20, 30, 0.95)' }} // Solid high-contrast background
                >
                    <div className="p-3 border-b border-white/10 bg-white/5">
                        <div className="text-xs text-gray-400 mb-1">Connected Wallet</div>
                        <div className="text-sm font-mono text-white break-all">
                            {address}
                        </div>
                    </div>

                    <div className="p-2">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                handleCopy();
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 transition-colors text-left group cursor-pointer"
                        >
                            {copied ? (
                                <Check className="w-4 h-4 text-green-400" />
                            ) : (
                                <Copy className="w-4 h-4 text-gray-400 group-hover:text-white" />
                            )}
                            <span className="text-sm text-gray-300 group-hover:text-white">
                                {copied ? 'Copied!' : 'Copy Address'}
                            </span>
                        </button>

                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                handleChangeWallet();
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 transition-colors text-left group cursor-pointer"
                        >
                            <RefreshCw className="w-4 h-4 text-gray-400 group-hover:text-white" />
                            <span className="text-sm text-gray-300 group-hover:text-white">
                                Change Wallet
                            </span>
                        </button>

                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                handleDisconnect();
                            }}
                            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-red-500/20 transition-colors text-left group cursor-pointer"
                        >
                            <LogOut className="w-4 h-4 text-gray-400 group-hover:text-red-400" />
                            <span className="text-sm text-gray-300 group-hover:text-red-400">
                                Disconnect
                            </span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
