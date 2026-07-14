// OmniSeed UI frontend — export panel
//
// Filter controls plus a download trigger. No client-side data
// transformation needed since the server (routes/export.js) does all
// the formatting.

export default function ExportPanel({ sourceType, dateFrom, dateTo }) {
  const download = (format) => {
    const params = new URLSearchParams({
      source_type: sourceType || '',
      from: dateFrom || '',
      to: dateTo || '',
    });
    window.location.href = `/api/export/${format}?${params}`;
  };

  return (
    <div className="flex gap-2">
      <button onClick={() => download('csv')}>Export CSV</button>
      <button onClick={() => download('json')}>Export JSON</button>
      <button onClick={() => download('pdf')}>Export PDF</button>
    </div>
  );
}
