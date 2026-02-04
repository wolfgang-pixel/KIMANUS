import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Tv,
  Play,
  Search,
  Globe,
  Clock,
  Sparkles,
  ArrowRight,
  Youtube,
  Brain,
  Languages,
} from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16 md:py-24">
        <div className="text-center max-w-4xl mx-auto">
          <div className="flex items-center justify-center gap-4 mb-6">
            <Tv className="w-16 h-16 text-purple-400" />
            <h1 className="text-5xl md:text-7xl font-bold text-white">
              Kim TV
            </h1>
          </div>
          <p className="text-xl md:text-2xl text-gray-300 mb-4">
            Dein KI-gestützter personalisierter Video-Kanal
          </p>
          <p className="text-gray-400 mb-8 max-w-2xl mx-auto">
            Sag uns, was dich interessiert. Unsere KI findet die besten YouTube-Videos
            und spielt die relevantesten Abschnitte - wie ein TV-Sender nur für dich.
          </p>
          <Link to="/watch">
            <Button size="lg" className="bg-purple-600 hover:bg-purple-700 text-lg px-8 py-6">
              <Play className="w-6 h-6 mr-2" />
              Jetzt starten
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Features Section */}
      <div className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-white text-center mb-12">
          So funktioniert's
        </h2>
        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <Card className="bg-black/40 border-purple-500/30">
            <CardContent className="p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-purple-600/20 flex items-center justify-center mx-auto mb-4">
                <Search className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">
                1. Thema wählen
              </h3>
              <p className="text-gray-400">
                Sag uns, was dich interessiert - von Programmierung bis Kochen,
                von Geschichte bis Musik.
              </p>
            </CardContent>
          </Card>

          <Card className="bg-black/40 border-purple-500/30">
            <CardContent className="p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-purple-600/20 flex items-center justify-center mx-auto mb-4">
                <Brain className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">
                2. KI analysiert
              </h3>
              <p className="text-gray-400">
                Unsere KI findet die besten Videos und berechnet die relevantesten
                Abschnitte für dich.
              </p>
            </CardContent>
          </Card>

          <Card className="bg-black/40 border-purple-500/30">
            <CardContent className="p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-purple-600/20 flex items-center justify-center mx-auto mb-4">
                <Tv className="w-8 h-8 text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">
                3. Zurücklehnen
              </h3>
              <p className="text-gray-400">
                Lehn dich zurück und genieße deinen personalisierten TV-Kanal
                mit Auto-Play und Loop-Modus.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Benefits Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-3xl font-bold text-white text-center mb-12">
            Warum Kim TV?
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="flex items-start gap-4 p-4 rounded-lg bg-black/20">
              <div className="w-10 h-10 rounded-full bg-green-600/20 flex items-center justify-center flex-shrink-0">
                <Globe className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <h4 className="font-semibold text-white mb-1">
                  Deutsche Inhalte bevorzugt
                </h4>
                <p className="text-sm text-gray-400">
                  Wir priorisieren deutschsprachige Kanäle aus Deutschland,
                  Österreich und der Schweiz.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg bg-black/20">
              <div className="w-10 h-10 rounded-full bg-blue-600/20 flex items-center justify-center flex-shrink-0">
                <Clock className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <h4 className="font-semibold text-white mb-1">
                  Zeit sparen
                </h4>
                <p className="text-sm text-gray-400">
                  Keine langen Intros oder irrelevanten Teile - direkt zum
                  interessanten Inhalt.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg bg-black/20">
              <div className="w-10 h-10 rounded-full bg-purple-600/20 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h4 className="font-semibold text-white mb-1">
                  KI-kuratiert
                </h4>
                <p className="text-sm text-gray-400">
                  Unsere KI analysiert Videos und findet die relevantesten
                  Abschnitte für dein Thema.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg bg-black/20">
              <div className="w-10 h-10 rounded-full bg-red-600/20 flex items-center justify-center flex-shrink-0">
                <Youtube className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h4 className="font-semibold text-white mb-1">
                  YouTube-Embedding
                </h4>
                <p className="text-sm text-gray-400">
                  Wir nutzen YouTube-Embedding - legal und sicher, wie mit
                  der Fernbedienung zappen.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Coming Soon Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-8">
            Bald verfügbar
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            <Card className="bg-black/30 border-white/10">
              <CardContent className="p-4">
                <Languages className="w-8 h-8 text-blue-400 mx-auto mb-2" />
                <h4 className="font-medium text-white text-sm">
                  Deutsche Untertitel
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  Für englische Videos
                </p>
              </CardContent>
            </Card>
            <Card className="bg-black/30 border-white/10">
              <CardContent className="p-4">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 mx-auto mb-2 flex items-center justify-center">
                  <span className="text-white text-xs font-bold">TTS</span>
                </div>
                <h4 className="font-medium text-white text-sm">
                  Vorgelesene Untertitel
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  Text-to-Speech
                </p>
              </CardContent>
            </Card>
            <Card className="bg-black/30 border-white/10">
              <CardContent className="p-4">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 mx-auto mb-2 flex items-center justify-center">
                  <span className="text-white text-lg">🤖</span>
                </div>
                <h4 className="font-medium text-white text-sm">
                  Avatar-Moderator
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  KI führt durch die Sendung
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="container mx-auto px-4 py-16 text-center">
        <h2 className="text-3xl font-bold text-white mb-4">
          Bereit für deinen eigenen TV-Kanal?
        </h2>
        <p className="text-gray-400 mb-8">
          Starte jetzt und entdecke die besten Videos zu deinen Lieblingsthemen.
        </p>
        <Link to="/watch">
          <Button size="lg" className="bg-purple-600 hover:bg-purple-700 text-lg px-8 py-6">
            <Play className="w-6 h-6 mr-2" />
            Jetzt Kim TV starten
          </Button>
        </Link>
      </div>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Tv className="w-4 h-4 text-purple-400" />
            <span className="text-gray-300">Kim TV</span>
          </div>
          <p>
            KI-gestützter Video-Kanal mit YouTube-Embedding
          </p>
          <p className="mt-2">
            Version 1.6.0
          </p>
        </div>
      </footer>
    </div>
  );
}
