import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { getSystemStatus } from './queries';

const inter = Inter({ subsets: ['latin'] });

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Arena Dashboard',
  description: 'Monitorowanie dostępności biletów na otwarte gry arenawalki.pl',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const nextScrapeTime = getSystemStatus('next_scrape_time');
  const formattedTime = nextScrapeTime 
    ? new Date(nextScrapeTime).toLocaleString('pl-PL') 
    : 'Oczekiwanie na scraper...';

  return (
    <html lang="pl" className="dark">
      <body className={`${inter.className} bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 min-h-screen`}>
        <div className="bg-blue-600 dark:bg-blue-700 text-white text-center py-2 text-sm font-medium shadow-sm">
          Kolejne sprawdzanie biletów: {formattedTime}
        </div>
        {children}
      </body>
    </html>
  );
}