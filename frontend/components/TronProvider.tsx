'use client';

import React from 'react';
import { WalletProvider } from '@tronweb3/tronwallet-adapter-react-hooks';
import { WalletModalProvider } from '@tronweb3/tronwallet-adapter-react-ui';
import { TronLinkAdapter } from '@tronweb3/tronwallet-adapters';

// Import wallet adapter CSS
import '@tronweb3/tronwallet-adapter-react-ui/style.css';

export function TronProvider({ children }: { children: React.ReactNode }) {
    const adapters = React.useMemo(() => {
        return [new TronLinkAdapter()];
    }, []);

    return (
        <WalletProvider adapters={adapters} autoConnect={true}>
            <WalletModalProvider>{children}</WalletModalProvider>
        </WalletProvider>
    );
}
