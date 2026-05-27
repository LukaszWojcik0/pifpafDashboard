'use client';

import { useState } from 'react';
import { useFormStatus } from 'react-dom';
import SelectorBuilder from './SelectorBuilder';

function SubmitBtn() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} className="w-full bg-blue-600 text-white font-medium py-2 rounded-lg hover:bg-blue-700 transition-colors mt-4">
      {pending ? 'Zapisywanie...' : 'Zapisz źródło'}
    </button>
  );
}

export default function SourceForm({ action }: { action: (formData: FormData) => void }) {
  const [preset, setPreset] = useState('custom');
  const [isApi, setIsApi] = useState('0');

  return (
    <form action={action} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Szablon konfiguracyjny</label>
        <select name="preset" value={preset} onChange={e => setPreset(e.target.value)} className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white bg-blue-50 dark:bg-blue-900/20 font-semibold text-blue-800 dark:text-blue-300">
          <option value="custom">🛠️ Własna konfiguracja (Custom)</option>
          <option value="playair">⚡ Szablon: PlayAir (Automatyczne API)</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nazwa (np. Miejscówka 2)</label>
        <input type="text" name="name" required className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
      </div>

      {preset === 'playair' ? (
        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
          <label className="block text-sm font-medium text-green-800 dark:text-green-300 mb-1">Link do areny PlayAir</label>
          <input type="url" name="playair_url" required={preset === 'playair'} placeholder="np. https://playair.pro/events/?arenaIds=8a801efc..." className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white mb-2" />
          <p className="text-xs text-green-700 dark:text-green-400">Skopiuj i wklej standardowy link do miejsca z PlayAir. System sam odnajdzie ID areny i ustawi poprawne API oraz selektory w tle.</p>
        </div>
      ) : (
        <>
          <details className="mb-6 bg-blue-50 dark:bg-blue-900/30 rounded-lg border border-blue-200 dark:border-blue-800">
            <summary className="p-3 font-semibold text-blue-800 dark:text-blue-300 cursor-pointer">ℹ️ Jak pobierać dane z API JSON innych stron? Kliknij!</summary>
            <div className="p-3 text-sm text-blue-900 dark:text-blue-200 space-y-2 border-t border-blue-200 dark:border-blue-800">
              <p>1. Wejdź na stronę docelową. Wciśnij <strong>F12</strong> i przejdź do zakładki <strong>Sieć (Network)</strong>.</p>
              <p>2. Zaznacz filtr <strong>Fetch/XHR</strong>. Odśwież stronę.</p>
              <p>3. Skopiuj jego <strong>Adres URL</strong> i wklej jako <i>Adres URL źródła</i> poniżej.</p>
              <p>4. Skopiuj cały tekst z zakładki <strong>Odpowiedź (Response)</strong> i wklej na dole strony do <i>Kreatora JSON</i>, aby wygenerować ścieżki.</p>
            </div>
          </details>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Typ pobierania danych</label>
            <select name="is_api" value={isApi} onChange={e => setIsApi(e.target.value)} className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
              <option value="0">🌐 Tradycyjna Strona HTML (Selektory CSS)</option>
              <option value="1">⚙️ Interfejs API (Ścieżki JSON)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Adres URL (HTML lub API)</label>
            <input type="url" name="list_url" required={preset === 'custom'} placeholder="https://..." className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">HTML: Linki wydarzeń / JSON: Ścieżka do tablicy</label>
            <input type="text" name="list_links_selector" placeholder='np. a.event-card LUB data.items' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Tytuł (CSS LUB Klucz JSON)</label>
            <input type="text" name="title_selector" placeholder="np. h1.title LUB name" className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Data</label>
              <input type="text" name="date_selector" placeholder='np. .date LUB startDate' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Czas</label>
              <input type="text" name="time_selector" placeholder='np. .time LUB startTime' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Obrazek (CSS LUB Klucz JSON)</label>
            <input type="text" name="image_selector" placeholder='np. meta[property="og:image"] LUB coverUrl' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Bilety (Regex HTML LUB Klucz JSON)</label>
            <input type="text" name="tickets_regex" placeholder='np. \((\d+) dostępnych\) LUB stock.available' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Wyprzedane Regex (HTML) LUB Klucz ID Wydarzenia (JSON)</label>
            <input type="text" name="sold_out_regex" placeholder='np. wyprzedane LUB id' className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
        </>
      )}

      <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-bold text-gray-900 dark:text-white mb-3">Customizacja Powiadomień (Opcjonalne)</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Indywidualny kanał NTFY (URL)</label>
            <input type="url" name="ntfy_url" placeholder="https://ntfy.sh/twoj-kanal-miejscowki" className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Szablon wiadomości ({'{title}'}, {'{available}'}, {'{max}'})</label>
            <input type="text" name="ntfy_template" placeholder="np. {title} ma dostępne {available} biletów!" className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
          </div>
        </div>
      </div>

      <SubmitBtn />
      {preset === 'custom' && <div className="mt-8"><SelectorBuilder /></div>}
    </form>
  );
}