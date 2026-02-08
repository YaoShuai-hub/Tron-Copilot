import { Header } from '@/components/Header';
import { ChatInterface } from '@/components/ChatInterface';
import { ParticleBackground } from '@/components/ParticleBackground';

export default function Home() {
    return (
        <div className="relative flex flex-col h-screen bg-black overflow-hidden">
            {/* Particle Background */}
            <ParticleBackground />

            {/* Animated gradient orbs */}
            <div className="fixed top-0 left-0 w-96 h-96 bg-tron-500/20 rounded-full blur-3xl animate-pulse" />
            <div className="fixed bottom-0 right-0 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />

            <div className="relative z-10 flex flex-col h-full">
                <Header />
                <ChatInterface />
            </div>
        </div>
    );
}
