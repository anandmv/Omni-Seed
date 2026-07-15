// OmniSeed UI backend — export route (SQLite)
//
// Queries analysis_results and formats to the requested type. Formatting
// happens entirely server-side so every view in the UI can trigger an
// export without duplicating formatting logic on the client.
//
// better-sqlite3 is synchronous, so no async/await is needed around queries.

import { Router } from 'express';
import { Parser as CsvParser } from 'json2csv';
import PDFDocument from 'pdfkit';
import db from '../db.js';

const router = Router();

router.get('/export/:format', (req, res) => {
  const { format } = req.params;
  const { source_type, from, to } = req.query;

  const rows = db
    .prepare(
      `SELECT source_id, source_type, summary, tags, anomaly_flag, measurements, system_fingerprint, created_at
       FROM analysis_results
       WHERE (@source_type IS NULL OR source_type = @source_type)
         AND (@from IS NULL OR created_at >= @from)
         AND (@to IS NULL OR created_at <= @to)
       ORDER BY created_at DESC`
    )
    .all({
      source_type: source_type || null,
      from: from || null,
      to: to || null,
    })
    .map((row) => ({
      ...row,
      tags: JSON.parse(row.tags || '[]'),
      measurements: JSON.parse(row.measurements || '{}'),
    }));

  switch (format) {
    case 'json':
      return res.json(rows);

    case 'csv': {
      const parser = new CsvParser({
        fields: ['source_id', 'source_type', 'summary', 'tags', 'anomaly_flag', 'measurements', 'system_fingerprint', 'created_at'],
      });
      res.header('Content-Type', 'text/csv');
      res.attachment('omniseed-export.csv');
      return res.send(parser.parse(rows));
    }

    case 'pdf': {
      const doc = new PDFDocument();
      res.header('Content-Type', 'application/pdf');
      res.attachment('omniseed-export.pdf');
      doc.pipe(res);
      doc.fontSize(16).text('OmniSeed Analysis Export', { underline: true });
      doc.moveDown();
      rows.forEach((row) => {
        doc.fontSize(11).text(`${row.created_at} — ${row.source_type} (${row.source_id})`);
        doc.fontSize(10).fillColor('gray').text(row.summary);
        if (row.measurements && Object.keys(row.measurements).length) {
          doc.fillColor('black').text(`Measurements: ${JSON.stringify(row.measurements)}`);
        }
        if (row.system_fingerprint) {
          doc.fillColor('blue').text(`Fingerprint: ${row.system_fingerprint}`);
        }
        if (row.anomaly_flag) doc.fillColor('red').text('Anomaly flagged');
        doc.fillColor('black').moveDown();
      });
      doc.end();
      return;
    }

    default:
      return res.status(400).json({ error: 'unsupported format' });
  }
});

export default router;
