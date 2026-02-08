'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useWallet } from '@tronweb3/tronwallet-adapter-react-hooks';

export type NetworkType = 'mainnet' | 'nile' | 'shasta' | 'unknown';

interface NetworkConfig {
    name: string;
    displayName: string;
    trongridUrl: string;
    tronscanUrl: string;
    tronscanApiUrl: string;
    color: string; // Badge color
}

interface NetworkContextType {
    network: NetworkType;
    config: NetworkConfig;
    isDetecting: boolean;
}

const NETWORK_CONFIGS: Record<NetworkType, NetworkConfig> = {
    mainnet: {
        name: 'mainnet',
        displayName: 'Mainnet',
        trongridUrl: 'https://api.trongrid.io',
        tronscanUrl: 'https://tronscan.org',
        tronscanApiUrl: 'https://apilist.tronscanapi.com/api',
        color: 'bg-green-500',
    },
    nile: {
        name: 'nile',
        displayName: 'Nile 测试网',
        trongridUrl: 'https://nile.trongrid.io',
        tronscanUrl: 'https://nile.tronscan.org',
        tronscanApiUrl: 'https://nileapi.tronscan.org/api',
        color: 'bg-orange-500',
    },
    shasta: {
        name: 'shasta',
        displayName: 'Shasta 测试网',
        trongridUrl: 'https://api.shasta.trongrid.io',
        tronscanUrl: 'https://shasta.tronscan.org',
        tronscanApiUrl: 'https://api.shasta.tronscan.org/api',
        color: 'bg-blue-500',
    },
    unknown: {
        name: 'unknown',
        displayName: 'Unknown Network',
        trongridUrl: 'https://nile.trongrid.io', // Default to Nile
        tronscanUrl: 'https://nile.tronscan.org',
        tronscanApiUrl: 'https://nileapi.tronscan.org/api',
        color: 'bg-gray-500',
    },
};

const NetworkContext = createContext<NetworkContextType>({
    network: 'nile', // Default to Nile for hackathon
    config: NETWORK_CONFIGS.nile,
    isDetecting: false,
});

export function NetworkProvider({ children }: { children: ReactNode }) {
    const { connected } = useWallet();
    const [network, setNetwork] = useState<NetworkType>('nile');
    const [isDetecting, setIsDetecting] = useState(false);

    useEffect(() => {
        if (!connected) {
            // Default to Nile when disconnected
            setNetwork('nile');
            return;
        }

        const detectNetwork = async () => {
            setIsDetecting(true);

            try {
                // Access TronWeb from window (injected by TronLink)
                const tronWeb = (window as any).tronWeb;

                if (!tronWeb?.fullNode?.host) {
                    console.warn('TronWeb fullNode not available, defaulting to Nile');
                    setNetwork('nile');
                    return;
                }

                const fullNodeUrl = tronWeb.fullNode.host.toLowerCase();
                console.log('[NetworkContext] Detected fullNode URL:', fullNodeUrl);

                // Detect network based on fullNode URL
                if (fullNodeUrl.includes('nile')) {
                    console.log('[NetworkContext] Network detected: Nile');
                    setNetwork('nile');
                } else if (fullNodeUrl.includes('shasta')) {
                    console.log('[NetworkContext] Network detected: Shasta');
                    setNetwork('shasta');
                } else if (
                    fullNodeUrl.includes('api.trongrid.io') ||
                    fullNodeUrl.includes('mainnet')
                ) {
                    console.log('[NetworkContext] Network detected: Mainnet');
                    setNetwork('mainnet');
                } else {
                    console.warn('Unknown network:', fullNodeUrl);
                    setNetwork('unknown');
                }
            } catch (error) {
                console.error('Failed to detect network:', error);
                setNetwork('nile'); // Fallback to Nile
            } finally {
                setIsDetecting(false);
            }
        };

        detectNetwork();

        // Listen for network changes (TronLink emits events)
        const handleNetworkChange = () => {
            console.log('Network changed, re-detecting...');
            detectNetwork();
        };

        window.addEventListener('message', (e) => {
            if (e.data.message?.action === 'setNode') {
                handleNetworkChange();
            }
        });

        return () => {
            window.removeEventListener('message', handleNetworkChange);
        };
    }, [connected]);

    return (
        <NetworkContext.Provider
            value={{
                network,
                config: NETWORK_CONFIGS[network],
                isDetecting,
            }}
        >
            {children}
        </NetworkContext.Provider>
    );
}

export function useNetwork() {
    const context = useContext(NetworkContext);
    if (!context) {
        throw new Error('useNetwork must be used within NetworkProvider');
    }
    return context;
}
