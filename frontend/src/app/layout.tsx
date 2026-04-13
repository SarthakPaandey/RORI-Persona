import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Persona Chat',
  description:
    'Chat with an AI representative to learn about background, skills, projects, and book an interview.',
};

 export default function RootLayout({
   children,
 }: {
   children: React.ReactNode;
 }) {
   return (
     <html lang="en">
       <head>
         <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
       </head>
       <body className="bg-gray-50 min-h-screen">{children}</body>
     </html>
   );
 }
