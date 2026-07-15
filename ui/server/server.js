import express from 'express';
import exportRouter from './routes/export.js';
import dashboardRouter from './routes/dashboard.js';

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static('public'));

app.use('/api', exportRouter);
app.use('/api', dashboardRouter);

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'OmniSeed UI server' });
});

app.use((req, res) => {
  res.status(404).json({ error: 'not found' });
});

app.listen(port, () => {
  console.log(`OmniSeed UI server listening on http://localhost:${port}`);
});
