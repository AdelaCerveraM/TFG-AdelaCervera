const { Client, LocalAuth } = require('whatsapp-web.js');
const axios = require('axios');
const qrcode = require('qrcode-terminal');
const express = require('express');
const bodyParser = require('body-parser');

const app = express();
const port = 3001;

app.use(bodyParser.json());

// Inicializa cliente de WhatsApp con sesión persistente
const client = new Client({
  authStrategy: new LocalAuth({
    clientId: "klaria-session"
  }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  }
});

// Muestra QR para escanear
client.on('qr', qr => {
  console.log('Escanea este QR con tu WhatsApp:\n');
  qrcode.generate(qr, { small: true });
});

// Notifica cuando está listo
client.on('ready', () => {
  console.log('WhatsApp conectado y escuchando mensajes.');
});

// Escucha mensajes entrantes y los reenvía al backend Flask
client.on('message', async message => {
  const contacto = await message.getContact();
  const remitente = contacto.pushname || contacto.number;
  const texto = message.body;

  if (!texto) return;

  axios.post('http://localhost:8000/api/insertar_whatsapp', {
    remitente: remitente,
    mensaje: texto
  }).then(() => {
    console.log(`Guardado: ${remitente}: ${texto}`);
  }).catch(err => {
    console.error("Error al comunicar con Flask:", err.message);
  });
});


// Endpoint para enviar mensajes desde Flask
app.post('/enviar_mensaje', async (req, res) => {
  const { numero, mensaje } = req.body;
  try {
    const numeroFormateado = numero.includes('@c.us') ? numero : `${numero}@c.us`;
    await client.sendMessage(numeroFormateado, mensaje);
    console.log(`Mensaje enviado a ${numero}: ${mensaje}`);
    res.status(200).send({ estado: 'enviado' });
  } catch (error) {
    console.error('Error al enviar mensaje:', error);
    res.status(500).send({ error: 'Fallo en el envío' });
  }
});

// Lanza el servidor Express
app.listen(port, () => {
  console.log(`Microservicio WhatsApp escuchando en http://localhost:${port}`);
});

// Inicializa cliente de WhatsApp
client.initialize();
