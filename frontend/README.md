# TRON Asset Management Copilot - Frontend

High-performance Next.js 14 frontend for TRON blockchain AI assistant.

## 🚀 Features

- **Real-time AI Streaming**: Non-blocking UI with efficient token streaming
- **TRON Wallet Integration**: Seamless TronLink wallet connection
- **Transaction Preview**: Smart JSON parsing for transaction cards
- **Glassmorphism UI**: Modern dark mode with frosted glass effects
- **Performance Optimized**: Virtualized lists, React.memo, 60FPS animations

## 📦 Tech Stack

- **Framework**: Next.js 14 (App Router + Turbopack)
- **Language**: TypeScript (Strict Mode)
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Web3**: TRON Wallet Adapter + TronWeb
- **AI**: Vercel AI SDK
- **Virtualization**: react-virtuoso

## 🛠️ Installation

```bash
cd frontend
npm install
```

## 🔧 Configuration

Create `.env.local`:

```env
MCP_SERVER_URL=http://localhost:8000
NEXT_PUBLIC_TRONGRID_API=https://api.trongrid.io
```

## 🚀 Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## 📁 Project Structure

```
frontend/
├── app/                    # Next.js App Router
│   ├── api/chat/          # AI streaming endpoint
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Main page
│   └── globals.css        # Global styles
├── components/            # React components
│   ├── ChatInterface.tsx  # Main chat UI
│   ├── ChatMessage.tsx    # Message component
│   ├── TransactionCard.tsx # Tx preview
│   ├── Header.tsx         # App header
│   └── TronProvider.tsx   # Wallet provider
├── lib/                   # Utilities
│   ├── store.ts          # Zustand store
│   └── stream-parser.ts  # JSON parser
└── types/                # TypeScript types
    └── chat.ts           # Chat & Tx types
```

## 🎯 Key Features

### Smart Stream Parsing

AI responses can include transaction data marked with `<<<JSON...JSON>>>`:

```
"Here's your transfer: <<<JSON{"txID":"..."}JSON>>> Ready to sign?"
```

The stream parser automatically detects and extracts transaction data.

### Non-Blocking Wallet Signing

When signing transactions:
- ✅ Only the transaction card shows loading state
- ✅ Rest of UI remains interactive
- ✅ User can scroll, view history, etc.

### Performance Optimization

- **React.memo**: Messages don't re-render on new tokens
- **Virtualization**: Smooth scrolling with 10,000+ messages
- **Code Splitting**: Lazy load heavy components
- **Zustand**: No Context API re-render issues

## 🧪 Testing

```bash
# Type check
npm run type-check

# Lint
npm run lint

# Build
npm run build
```

## 📱 Mobile Support

Fully responsive design optimized for:
- Desktop (1920x1080+)
- Tablet (768px+)
- Mobile (375px+)

## 🎨 Design System

### Colors
- Primary: TRON Blue (#3b82f6)
- Background: Dark gradient
- Glassmorphism: rgba(255,255,255,0.05)

### Animations
- Message fade-in: 200ms
- Transaction slide-up: 300ms
- Button hover: 150ms

## 🔒 Security

- No private keys stored
- All signing done in wallet
- Transactions previewed before execution

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome! Please open an issue first.

---

Built with ❤️ for TRON Hackathon
