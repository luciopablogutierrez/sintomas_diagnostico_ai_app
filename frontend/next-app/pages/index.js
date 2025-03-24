import { useState, useRef, useEffect } from 'react';
import Head from 'next/head';
import toast, { Toaster } from 'react-hot-toast';

export default function Home() {
  const [symptoms, setSymptoms] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const messagesEndRef = useRef(null);

  // Función para desplazarse al final de los mensajes
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Función para enviar síntomas al backend
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!symptoms.trim()) {
      toast.error('Por favor, ingrese los síntomas del paciente');
      return;
    }
    
    // Agregar mensaje del usuario
    setMessages(prev => [...prev, { role: 'user', content: symptoms }]);
    
    // Mostrar indicador de carga
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symptoms }),
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Formatear la respuesta
      const formattedResponse = {
        role: 'assistant',
        content: data.diagnosis,
        matches: data.matches
      };
      
      // Agregar respuesta al historial
      setMessages(prev => [...prev, formattedResponse]);
      
      // Limpiar campo de entrada
      setSymptoms('');
    } catch (error) {
      console.error('Error:', error);
      toast.error('Error al procesar la solicitud. Inténtelo de nuevo.');
      
      // Agregar mensaje de error
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Lo siento, ha ocurrido un error al procesar su solicitud. Por favor, inténtelo de nuevo.'
      }]);
    } finally {
      setIsLoading(false);
    }