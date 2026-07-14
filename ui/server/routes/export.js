// OmniSeed UI backend — export route
//
// Queries analysis_results and formats to the requested type. Formatting
// happens entirely server-side so every view in the UI can trigger an
// export without duplicating formatting logic on the client.

import { Router } from 'express';
import { Parser as CsvParser } from 'json2csv';
import PDFDocument from 'pdfkit';
import db from '../db.js';

const router = Router();

router.get('/export/:format', async (req, res) => {
  const { format } = req.params;
  const { source_type, from, to } = req.query;

  const results = await db.query(
    `SELECT source_id, source_type, summary, tags, anomaly_flag, created_at
     FROM analysis_results
     WHERE ($1::text IS NULL OR source_type = $1)
       AND ($2::timestamptz IS NULL OR created_at >= $2)
       AND ($3::timestamptz IS NULL OR created_at <= $3)
     ORDER BY created_at DESC`,
    [source_type || null, from || null, to || null]
  );

  switch (format) {
    case 'json':
      return res.json(results.rows);

    case 'csv': {
      const parser = new CsvParser({
        fields: ['source_id', 'source_type', 'summary', 'tags', 'anomaly_flag', 'created_at'],
      });
      res.header('Content-Type', 'text/csv');
      res.attachment('omniseed-export.csv');
      return res.send(parser.parse(results.rows));
    }

    case 'pdf': {
      const doc = new PDFDocument();
      res.header('Content-Type', 'application/pdf');
      res.attachment('omniseed-export.pdf');
      doc.pipe(res);
      doc.fontSize(16).text('OmniSeed Analysis Export', { underline: true });
      doc.moveDown();
      results.rows.forEach((row) => {
        doc.fontSize(11).text(`${row.created_at.toISOString()} — ${row.source_type} (${row.source_id})`);
        doc.fontSize(10).fillColor('gray').text(row.summary);
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
