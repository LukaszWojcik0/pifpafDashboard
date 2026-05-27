'use client';

import { useState, MouseEvent } from 'react';

export default function SelectorBuilder() {
  const [html, setHtml] = useState('');
  const [selectedSelector, setSelectedSelector] = useState('');

  const generateSelector = (el: HTMLElement): string => {
    if (!el || el.nodeType !== 1) return '';
    let sel = el.tagName.toLowerCase();

    // Jeśli element ma ID, jest ono najbardziej precyzyjne
    if (el.id) {
      return `${sel}#${el.id}`;
    }

    // Bardzo przydatne dla systemów typu PlayAir - szukanie stałych atrybutów "data-*"
    const dataAttrs = Array.from(el.attributes).filter(attr => attr.name.startsWith('data-'));
    if (dataAttrs.length > 0) {
      return `${sel}[${dataAttrs[0].name}="${dataAttrs[0].value}"]`;
    }

    // Próba budowy selektora na bazie klas, omijając wygenerowane przez React/StyledComponents "sc-*"
    if (el.className && typeof el.className === 'string') {
      // svg icons w fontawesome mogą sprawiać problemy jako string
      try {
        const classes = el.className.split(' ').filter(c => c.trim() && !c.startsWith('sc-') && !c.startsWith('hover:'));
        if (classes.length > 0) {
          sel += '.' + classes.join('.');
        }
      } catch (e) {
         // Ignore SVG className objects
      }
    }
    return sel;
  };

  const handlePreviewClick = (e: MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const target = e.target as HTMLElement;
    const sel = generateSelector(target);
    setSelectedSelector(sel);
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-700 mt-8 shadow-inner">
      <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">🛠️ Narzędzie: Interaktywny Kreator Selektorów</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Nie wiesz jak wpisać selektor? Skopiuj kod HTML za pomocą <strong>Zbadaj Element</strong> w przeglądarce i wklej go poniżej. Następnie kliknij interesujący Cię fragment (tytuł, data) na wygenerowanym podglądzie. Narzędzie automatycznie przygotuje optymalny selektor, pomijając dynamiczne klasy!
      </p>
      
      <textarea 
        className="w-full p-3 text-sm border rounded-lg dark:bg-gray-800 dark:border-gray-600 dark:text-gray-300 mb-4 h-32 font-mono focus:ring-2 focus:ring-blue-500"
        placeholder='Wklej kod HTML tutaj (np. <div class="event-card">...</div>)'
        value={html}
        onChange={e => setHtml(e.target.value)}
      />
      
      {html && (
        <div className="flex flex-col-reverse md:flex-row gap-6 items-start relative">
          <div className="flex-1 border border-blue-300 dark:border-blue-700 p-4 rounded-lg bg-white dark:bg-gray-800 overflow-auto cursor-crosshair shadow-sm w-full" onClick={handlePreviewClick}>
            <p className="text-xs text-blue-500 font-bold mb-3 uppercase tracking-wide border-b border-blue-100 dark:border-blue-800 pb-2">🎯 Kliknij w element poniżej:</p>
            <div dangerouslySetInnerHTML={{ __html: html }} className="pointer-events-auto [&_svg]:max-w-[2.5rem] [&_svg]:max-h-[2.5rem] [&_svg]:inline-block" />
          </div>
          
          <div className="w-full md:w-1/3 sticky top-4 bg-white dark:bg-gray-800 p-5 rounded-xl border border-blue-200 dark:border-blue-800 shadow-md z-10 transition-all">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Wygenerowany selektor (skopiuj do formularza):</p>
            <code className="block p-4 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm break-all text-blue-600 dark:text-blue-400 border border-gray-200 dark:border-gray-700 selection:bg-blue-200">
              {selectedSelector || 'Wybierz element z podglądu obok...'}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}