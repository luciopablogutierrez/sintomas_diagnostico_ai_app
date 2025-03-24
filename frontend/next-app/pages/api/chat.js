export default async function handler(req, res) {
  if (req.method === 'POST') {
    try {
      // Conexión directa sin middleware adicional
      const response = await fetch('http://localhost:8000/diagnose', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symptoms: req.body.symptoms}),
        cache: 'no-store' // Para datos siempre frescos
      });
      
      const data = await response.json();
      res.status(200).json(data);
    } catch (error) {
      res.status(500).json({error: 'Prediction failed'});
    }
  } else {
    res.status(405).json({error: 'Method not allowed'});
  }
}