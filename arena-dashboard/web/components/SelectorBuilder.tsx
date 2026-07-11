'use client';

import { ChangeEvent, MouseEvent, useState } from 'react';
import { buildPreviewSrcDoc, HTML_PREVIEW_IFRAME_SANDBOX } from './htmlPreviewSecurity.mjs';

type JsonViewerProps = {
  data: unknown;
  path?: string;
  onSelect: (path: string) => void;
};

const JsonViewer = ({ data, path = '', onSelect }: JsonViewerProps) => {
  const isArray = Array.isArray(data);
  const isObject = data !== null && typeof data === 'object';

  if (!isObject) {
    return (
      <span
        className="text-green-600 dark:text-green-400 cursor-pointer hover:bg-yellow-200 dark:hover:bg-yellow-800/50 rounded px-1 transition-colors"
        onClick={(event) => {
          event.stopPropagation();
          onSelect(path);
        }}
      >
        {JSON.stringify(data)}
      </span>
    );
  }

  return (
    <div className="pl-4 border-l border-gray-300 dark:border-gray-600 ml-2 my-1 text-sm font-mono break-all">
      <span
        className="text-gray-400 select-none cursor-pointer hover:text-gray-600"
        onClick={(event) => {
          event.stopPropagation();
          onSelect(path);
        }}
      >
        {isArray ? '[' : '{'}
      </span>
      {Object.entries(data).map(([key, value]) => {
        const currentPath = path ? (isArray ? `${path}[${key}]` : `${path}.${key}`) : key;
        return (
          <div key={key} className="my-1">
            {!isArray && (
              <span
                className="text-blue-600 dark:text-blue-400 font-medium cursor-pointer hover:bg-yellow-200 dark:hover:bg-yellow-800/50 rounded px-1 transition-colors"
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(currentPath);
                }}
              >
                &quot;{key}&quot;:
              </span>
            )}
            {isArray && <span className="text-gray-500 text-xs mr-1">{key}:</span>}
            <span className="ml-1">
              <JsonViewer data={value} path={currentPath} onSelect={onSelect} />
            </span>
          </div>
        );
      })}
      <span
        className="text-gray-400 select-none cursor-pointer hover:text-gray-600"
        onClick={(event) => {
          event.stopPropagation();
          onSelect(path);
        }}
      >
        {isArray ? ']' : '}'}
      </span>
    </div>
  );
};

export default function SelectorBuilder() {
  const [inputData, setInputData] = useState('');
  const [selectedSelector, setSelectedSelector] = useState('');
  const [mode, setMode] = useState<'html' | 'json'>('html');
  const [jsonObj, setJsonObj] = useState<unknown>(null);

  const handleInputChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    const value = event.target.value;
    setInputData(value);
    if (mode === 'json') {
      try {
        setJsonObj(JSON.parse(value));
      } catch {
        setJsonObj(null);
      }
    }
  };

  const switchMode = (newMode: 'html' | 'json') => {
    setMode(newMode);
    setSelectedSelector('');
    if (newMode === 'json') {
      try {
        setJsonObj(JSON.parse(inputData));
      } catch {
        setJsonObj(null);
      }
    }
  };

  const generateSelector = (element: HTMLElement): string => {
    if (!element || element.nodeType !== 1) return '';
    let selector = element.tagName.toLowerCase();

    if (element.id) {
      return `${selector}#${element.id}`;
    }

    const dataAttrs = Array.from(element.attributes).filter((attr) => attr.name.startsWith('data-'));
    if (dataAttrs.length > 0) {
      return `${selector}[${dataAttrs[0].name}="${dataAttrs[0].value}"]`;
    }

    if (element.className && typeof element.className === 'string') {
      const classes = element.className
        .split(' ')
        .filter((className) => className.trim() && !className.startsWith('sc-') && !className.startsWith('hover:'));
      if (classes.length > 0) {
        selector += `.${classes.join('.')}`;
      }
    }
    return selector;
  };

  const handleJsonPreviewClick = (event: MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const target = event.target as HTMLElement;
    setSelectedSelector(generateSelector(target));
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-700 mt-8 shadow-inner">
      <h3 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">Interaktywny kreator selektorow</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        Wybierz z czym pracujesz, wklej kod HTML lub obiekt JSON. Dla JSON kliknij pole, aby zbudowac sciezke.
      </p>

      <div className="flex gap-2 mb-4">
        <button onClick={() => switchMode('html')} className={`px-4 py-2 rounded-lg font-medium transition-colors ${mode === 'html' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-800 dark:text-gray-300'}`}>Tryb HTML</button>
        <button onClick={() => switchMode('json')} className={`px-4 py-2 rounded-lg font-medium transition-colors ${mode === 'json' ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300 dark:bg-gray-800 dark:text-gray-300'}`}>Tryb API JSON</button>
      </div>

      <textarea
        className="w-full p-3 text-sm border rounded-lg dark:bg-gray-800 dark:border-gray-600 dark:text-gray-300 mb-4 h-32 font-mono focus:ring-2 focus:ring-blue-500"
        placeholder={mode === 'html' ? 'Wklej kod HTML tutaj...' : 'Wklej odpowiedz z API w formacie JSON...'}
        value={inputData}
        onChange={handleInputChange}
      />

      {inputData && (
        <div className="flex flex-col-reverse md:flex-row gap-6 items-start relative">
          <div
            className={`flex-1 border p-4 rounded-lg bg-white dark:bg-gray-800 overflow-auto shadow-sm w-full ${mode === 'html' ? 'border-blue-300 dark:border-blue-700' : 'border-green-300 dark:border-green-700'}`}
            onClick={mode === 'json' ? handleJsonPreviewClick : undefined}
          >
            <p className={`text-xs font-bold mb-3 uppercase tracking-wide border-b pb-2 ${mode === 'html' ? 'text-blue-500 border-blue-100 dark:border-blue-800' : 'text-green-500 border-green-100 dark:border-green-800'}`}>
              {mode === 'html' ? 'Izolowany podglad HTML' : 'Kliknij w dowolny klucz JSON lub zawartosc:'}
            </p>
            {mode === 'html' ? (
              <iframe
                title="Izolowany podglad HTML"
                sandbox={HTML_PREVIEW_IFRAME_SANDBOX}
                referrerPolicy="no-referrer"
                srcDoc={buildPreviewSrcDoc(inputData)}
                className="w-full min-h-[24rem] rounded border border-gray-200 bg-white"
              />
            ) : jsonObj ? (
              <JsonViewer data={jsonObj} onSelect={setSelectedSelector} />
            ) : (
              <p className="text-red-500 font-mono text-sm">Blad parsowania: skopiowany tekst nie jest prawidlowym formatem JSON.</p>
            )}
          </div>

          <div className={`w-full md:w-1/3 sticky top-4 bg-white dark:bg-gray-800 p-5 rounded-xl border shadow-md z-10 transition-all ${mode === 'html' ? 'border-blue-200 dark:border-blue-800' : 'border-green-200 dark:border-green-800'}`}>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Wygenerowany selektor:</p>
            <code className={`block p-4 bg-gray-100 dark:bg-gray-900 rounded-lg font-mono text-sm break-all border border-gray-200 dark:border-gray-700 ${mode === 'html' ? 'text-blue-600 dark:text-blue-400 selection:bg-blue-200' : 'text-green-600 dark:text-green-400'}`}>
              {selectedSelector || (mode === 'html' ? 'Podglad HTML jest izolowany.' : 'Wybierz element z podgladu obok...')}
            </code>
            {mode === 'json' && selectedSelector && selectedSelector.includes('[') && (
              <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded border border-green-200 dark:border-green-800">
                <p className="text-xs text-gray-500 mb-1">Dla list uzyj sciezki wzglednej:</p>
                <code className="font-mono text-sm text-green-700 dark:text-green-400 font-bold select-all">
                  {selectedSelector.match(/\[\d+\]\.(.*)/)?.[1] || selectedSelector}
                </code>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
