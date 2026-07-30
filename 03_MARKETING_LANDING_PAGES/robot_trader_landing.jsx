import React, { useState } from 'react';
import { ChevronDown, Mail, TrendingUp, BarChart3, Zap, Globe, ArrowRight } from 'lucide-react';

const RobotTraderLanding = () => {
  const [lang, setLang] = useState('IT');
  const [email, setEmail] = useState('');
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [activeTab, setActiveTab] = useState('azioni');

  const translations = {
    IT: {
      nav: { home: 'Home', services: 'Servizi', pricing: 'Prezzi', demo: 'Demo', contact: 'Contatti' },
      hero: {
        title: 'Scopri Opportunità Nascoste',
        subtitle: 'Screener automatici per valore, ogni giorno. Deep value investing reso semplice.',
        cta: 'Ricevi Report di Prova Gratuito'
      },
      products: {
        title: 'I Nostri Screener',
        azioni: {
          name: 'Value Screener AZIONI',
          desc: '1.286 ticker globali analizzati ogni giorno',
          features: ['S&P 500, Russell 2000, FTSE, DAX, CAC', 'Filtri EV/FCF, P/B, ROE', 'Deep Value Strategy']
        },
        etf: {
          name: 'Value Screener ETF',
          desc: '59 ETF selezionati per qualità e costo',
          features: ['TER < 0.50%', 'AUM > 100M EUR', 'Sharpe Ratio > 0.5']
        },
        fondi: {
          name: 'Value Screener FONDI',
          desc: '59 fondi UCITS europei di qualità',
          features: ['TER < 1.00%', 'AUM > 500M EUR', 'Performance tracking']
        }
      },
      benefits: {
        title: 'Perché Robot Trader?',
        items: [
          { icon: 'Zap', title: 'Automazione Totale', desc: 'Email giornaliera alle 08:05 con risultati freschi' },
          { icon: 'Globe', title: 'Copertura Globale', desc: '1.404+ strumenti finanziari monitorati' },
          { icon: 'TrendingUp', title: 'Strategie Provate', desc: 'Deep value screening basato su metriche solide' },
          { icon: 'BarChart3', title: 'Dati Professionale', desc: 'Excel dettagliato con analisi completa' }
        ]
      },
      pricing: {
        title: 'Prezzi Trasparenti',
        azioni: { price: '€49', period: '/mese', desc: 'Value Screener Azioni' },
        etf: { price: '€79', period: '/mese', desc: 'Value Screener ETF' },
        fondi: { price: '€99', period: '/mese', desc: 'Value Screener Fondi' },
        bundle: { price: '€149', period: '/mese', desc: 'Bundle Completo (ENTERPRISE)' }
      },
      demo: {
        title: 'Vedi i Risultati',
        subtitle: 'Questo è quello che riceverai ogni giorno',
        tabs: { azioni: 'Azioni', etf: 'ETF', fondi: 'Fondi' }
      },
      cta: {
        title: 'Pronto a Scoprire Opportunità?',
        subtitle: 'Ricevi subito un report di prova con 20 azioni selezionate',
        placeholder: 'La tua email',
        button: 'Ricevi Report Gratuito',
        success: 'Grazie! Controlla la tua email.'
      },
      footer: {
        company: 'Fuerte Venture Capital',
        rights: '© 2026 NCF New Capital Fuerte SL. Tutti i diritti riservati.',
        contact: 'Contatti'
      }
    },
    ES: {
      nav: { home: 'Inicio', services: 'Servicios', pricing: 'Precios', demo: 'Demo', contact: 'Contacto' },
      hero: {
        title: 'Descubre Oportunidades Ocultas',
        subtitle: 'Screeners automáticos de valor, cada día. Value investing hecho simple.',
        cta: 'Recibe Reporte de Prueba Gratis'
      },
      products: {
        title: 'Nuestros Screeners',
        azioni: {
          name: 'Value Screener ACCIONES',
          desc: '1.286 tickers globales analizados diariamente',
          features: ['S&P 500, Russell 2000, FTSE, DAX, CAC', 'Filtros EV/FCF, P/B, ROE', 'Estrategia Deep Value']
        },
        etf: {
          name: 'Value Screener ETF',
          desc: '59 ETF seleccionados por calidad y coste',
          features: ['TER < 0.50%', 'AUM > 100M EUR', 'Sharpe Ratio > 0.5']
        },
        fondi: {
          name: 'Value Screener FONDOS',
          desc: '59 fondos UCITS europeos de calidad',
          features: ['TER < 1.00%', 'AUM > 500M EUR', 'Seguimiento de rendimiento']
        }
      },
      benefits: {
        title: '¿Por qué Robot Trader?',
        items: [
          { icon: 'Zap', title: 'Automatización Total', desc: 'Email diario a las 08:05 con resultados frescos' },
          { icon: 'Globe', title: 'Cobertura Global', desc: '1.404+ instrumentos financieros monitoreados' },
          { icon: 'TrendingUp', title: 'Estrategias Probadas', desc: 'Deep value screening basado en métricas sólidas' },
          { icon: 'BarChart3', title: 'Datos Profesionales', desc: 'Excel detallado con análisis completo' }
        ]
      },
      pricing: {
        title: 'Precios Transparentes',
        azioni: { price: '€49', period: '/mes', desc: 'Value Screener Acciones' },
        etf: { price: '€79', period: '/mes', desc: 'Value Screener ETF' },
        fondi: { price: '€99', period: '/mes', desc: 'Value Screener Fondos' },
        bundle: { price: '€149', period: '/mes', desc: 'Bundle Completo (ENTERPRISE)' }
      },
      demo: {
        title: 'Ve los Resultados',
        subtitle: 'Esto es lo que recibirás cada día',
        tabs: { azioni: 'Acciones', etf: 'ETF', fondi: 'Fondos' }
      },
      cta: {
        title: '¿Listo para Descubrir Oportunidades?',
        subtitle: 'Recibe ahora un reporte de prueba con 20 acciones seleccionadas',
        placeholder: 'Tu email',
        button: 'Recibe Reporte Gratis',
        success: '¡Gracias! Revisa tu correo.'
      },
      footer: {
        company: 'Fuerte Venture Capital',
        rights: '© 2026 NCF New Capital Fuerte SL. Todos los derechos reservados.',
        contact: 'Contacto'
      }
    },
    EN: {
      nav: { home: 'Home', services: 'Services', pricing: 'Pricing', demo: 'Demo', contact: 'Contact' },
      hero: {
        title: 'Discover Hidden Opportunities',
        subtitle: 'Automated value screeners, every day. Deep value investing made simple.',
        cta: 'Get Free Trial Report'
      },
      products: {
        title: 'Our Screeners',
        azioni: {
          name: 'Value Screener EQUITIES',
          desc: '1.286 global tickers analyzed daily',
          features: ['S&P 500, Russell 2000, FTSE, DAX, CAC', 'EV/FCF, P/B, ROE filters', 'Deep Value Strategy']
        },
        etf: {
          name: 'Value Screener ETF',
          desc: '59 ETFs selected for quality and cost',
          features: ['TER < 0.50%', 'AUM > 100M EUR', 'Sharpe Ratio > 0.5']
        },
        fondi: {
          name: 'Value Screener FUNDS',
          desc: '59 quality European UCITS funds',
          features: ['TER < 1.00%', 'AUM > 500M EUR', 'Performance tracking']
        }
      },
      benefits: {
        title: 'Why Robot Trader?',
        items: [
          { icon: 'Zap', title: 'Full Automation', desc: 'Daily email at 08:05 with fresh results' },
          { icon: 'Globe', title: 'Global Coverage', desc: '1.404+ financial instruments monitored' },
          { icon: 'TrendingUp', title: 'Proven Strategies', desc: 'Deep value screening based on solid metrics' },
          { icon: 'BarChart3', title: 'Professional Data', desc: 'Detailed Excel with complete analysis' }
        ]
      },
      pricing: {
        title: 'Transparent Pricing',
        azioni: { price: '€49', period: '/month', desc: 'Value Screener Equities' },
        etf: { price: '€79', period: '/month', desc: 'Value Screener ETF' },
        fondi: { price: '€99', period: '/month', desc: 'Value Screener Funds' },
        bundle: { price: '€149', period: '/month', desc: 'Complete Bundle (ENTERPRISE)' }
      },
      demo: {
        title: 'See the Results',
        subtitle: 'This is what you\'ll receive every day',
        tabs: { azioni: 'Equities', etf: 'ETF', fondi: 'Funds' }
      },
      cta: {
        title: 'Ready to Discover Opportunities?',
        subtitle: 'Get a trial report with 20 selected equities',
        placeholder: 'Your email',
        button: 'Get Free Report',
        success: 'Thank you! Check your email.'
      },
      footer: {
        company: 'Fuerte Venture Capital',
        rights: '© 2026 NCF New Capital Fuerte SL. All rights reserved.',
        contact: 'Contact'
      }
    },
    FR: {
      nav: { home: 'Accueil', services: 'Services', pricing: 'Tarifs', demo: 'Démo', contact: 'Contact' },
      hero: {
        title: 'Découvrez des Opportunités Cachées',
        subtitle: 'Screeners automatisés de valeur, chaque jour. L\'investissement value rendu simple.',
        cta: 'Obtenir un Rapport d\'Essai Gratuit'
      },
      products: {
        title: 'Nos Screeners',
        azioni: {
          name: 'Value Screener ACTIONS',
          desc: '1.286 tickers mondiaux analysés quotidiennement',
          features: ['S&P 500, Russell 2000, FTSE, DAX, CAC', 'Filtres EV/FCF, P/B, ROE', 'Stratégie Deep Value']
        },
        etf: {
          name: 'Value Screener ETF',
          desc: '59 ETF sélectionnés pour la qualité et le coût',
          features: ['TER < 0.50%', 'AUM > 100M EUR', 'Ratio de Sharpe > 0.5']
        },
        fondi: {
          name: 'Value Screener FONDS',
          desc: '59 fonds OPCVM européens de qualité',
          features: ['TER < 1.00%', 'AUM > 500M EUR', 'Suivi des performances']
        }
      },
      benefits: {
        title: 'Pourquoi Robot Trader?',
        items: [
          { icon: 'Zap', title: 'Automatisation Complète', desc: 'Email quotidien à 08:05 avec résultats frais' },
          { icon: 'Globe', title: 'Couverture Mondiale', desc: '1.404+ instruments financiers surveillés' },
          { icon: 'TrendingUp', title: 'Stratégies Éprouvées', desc: 'Deep value screening basé sur des métriques solides' },
          { icon: 'BarChart3', title: 'Données Professionnelles', desc: 'Excel détaillé avec analyse complète' }
        ]
      },
      pricing: {
        title: 'Tarifs Transparents',
        azioni: { price: '€49', period: '/mois', desc: 'Value Screener Actions' },
        etf: { price: '€79', period: '/mois', desc: 'Value Screener ETF' },
        fondi: { price: '€99', period: '/mois', desc: 'Value Screener Fonds' },
        bundle: { price: '€149', period: '/mois', desc: 'Pack Complet (ENTERPRISE)' }
      },
      demo: {
        title: 'Voir les Résultats',
        subtitle: 'Voici ce que vous recevrez chaque jour',
        tabs: { azioni: 'Actions', etf: 'ETF', fondi: 'Fonds' }
      },
      cta: {
        title: 'Prêt à Découvrir des Opportunités?',
        subtitle: 'Obtenir un rapport d\'essai avec 20 actions sélectionnées',
        placeholder: 'Votre email',
        button: 'Obtenir un Rapport Gratuit',
        success: 'Merci! Vérifiez votre email.'
      },
      footer: {
        company: 'Fuerte Venture Capital',
        rights: '© 2026 NCF New Capital Fuerte SL. Tous droits réservés.',
        contact: 'Contact'
      }
    },
    DE: {
      nav: { home: 'Startseite', services: 'Dienstleistungen', pricing: 'Preise', demo: 'Demo', contact: 'Kontakt' },
      hero: {
        title: 'Entdecken Sie Verborgene Chancen',
        subtitle: 'Automatisierte Value-Screener jeden Tag. Value Investing leicht gemacht.',
        cta: 'Kostenlosen Testbericht Erhalten'
      },
      products: {
        title: 'Unsere Screener',
        azioni: {
          name: 'Value Screener AKTIEN',
          desc: '1.286 globale Tickers täglich analysiert',
          features: ['S&P 500, Russell 2000, FTSE, DAX, CAC', 'EV/FCF, P/B, ROE Filter', 'Deep-Value-Strategie']
        },
        etf: {
          name: 'Value Screener ETF',
          desc: '59 ETFs ausgewählt für Qualität und Kosten',
          features: ['TER < 0.50%', 'AUM > 100M EUR', 'Sharpe Ratio > 0.5']
        },
        fondi: {
          name: 'Value Screener FONDS',
          desc: '59 hochwertige europäische UCITS-Fonds',
          features: ['TER < 1.00%', 'AUM > 500M EUR', 'Performance-Verfolgung']
        }
      },
      benefits: {
        title: 'Warum Robot Trader?',
        items: [
          { icon: 'Zap', title: 'Vollständige Automatisierung', desc: 'Tägliche E-Mail um 08:05 mit frischen Ergebnissen' },
          { icon: 'Globe', title: 'Globale Abdeckung', desc: '1.404+ Finanzinstrumente überwacht' },
          { icon: 'TrendingUp', title: 'Bewährte Strategien', desc: 'Deep-Value-Screening basierend auf soliden Metriken' },
          { icon: 'BarChart3', title: 'Professionelle Daten', desc: 'Detaillierte Excel-Tabelle mit vollständiger Analyse' }
        ]
      },
      pricing: {
        title: 'Transparente Preise',
        azioni: { price: '€49', period: '/Monat', desc: 'Value Screener Aktien' },
        etf: { price: '€79', period: '/Monat', desc: 'Value Screener ETF' },
        fondi: { price: '€99', period: '/Monat', desc: 'Value Screener Fonds' },
        bundle: { price: '€149', period: '/Monat', desc: 'Komplettes Paket (ENTERPRISE)' }
      },
      demo: {
        title: 'Sehen Sie die Ergebnisse',
        subtitle: 'Das erhalten Sie jeden Tag',
        tabs: { azioni: 'Aktien', etf: 'ETF', fondi: 'Fonds' }
      },
      cta: {
        title: 'Bereit, Chancen zu Entdecken?',
        subtitle: 'Erhalten Sie sofort einen Testbericht mit 20 ausgewählten Aktien',
        placeholder: 'Ihre E-Mail',
        button: 'Kostenlosen Bericht Erhalten',
        success: 'Danke! Überprüfen Sie Ihre E-Mail.'
      },
      footer: {
        company: 'Fuerte Venture Capital',
        rights: '© 2026 NCF New Capital Fuerte SL. Alle Rechte vorbehalten.',
        contact: 'Kontakt'
      }
    }
  };

  const t = translations[lang];

  const mockData = {
    azioni: [
      { ticker: 'LEN', name: 'Lennar Corporation', evfcf: 5.20, pb: 0.89, roe: 15.2 },
      { ticker: 'NOV', name: 'NOV Inc.', evfcf: 10.66, pb: 0.92, roe: 12.1 },
      { ticker: 'MHK', name: 'Mohawk Industries', evfcf: 8.84, pb: 0.88, roe: 14.5 },
      { ticker: 'DXC', name: 'DXC Technology', evfcf: 5.91, pb: 0.75, roe: 11.8 },
      { ticker: 'SITC', name: 'SITE Centers', evfcf: 4.34, pb: 0.82, roe: 13.2 },
    ],
    etf: [
      { ticker: 'VWRL.L', name: 'Vanguard FTSE All-World', ter: 0.22, aum: 8500 },
      { ticker: 'SWDA.L', name: 'iShares Core MSCI World', ter: 0.20, aum: 65000 },
      { ticker: 'EUNL.L', name: 'iShares Core MSCI Europe', ter: 0.12, aum: 28000 },
    ],
    fondi: [
      { ticker: 'V60A.L', name: 'Vanguard LifeStrategy 60%', ter: 0.35, aum: 15200 },
      { ticker: 'IGLS.L', name: 'iShares Core Bond', ter: 0.10, aum: 22500 },
    ]
  };

  const handleEmailSubmit = (e) => {
    e.preventDefault();
    if (email) {
      setEmailSubmitted(true);
      setTimeout(() => setEmailSubmitted(false), 3000);
      setEmail('');
    }
  };

  return (
    <div style={{ 
      background: 'linear-gradient(135deg, #1a2b4a 0%, #0f1f35 100%)',
      color: '#e8e8e8',
      fontFamily: "'Playfair Display', 'Georgia', serif"
    }}>
      {/* Navbar */}
      <nav style={{ 
        padding: '1.5rem 2rem', 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        borderBottom: '1px solid rgba(255, 149, 0, 0.1)',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#FF9500' }}>
          🤖 ROBOT TRADER
        </div>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <select 
            value={lang} 
            onChange={(e) => setLang(e.target.value)}
            style={{
              background: 'rgba(255, 149, 0, 0.1)',
              border: '1px solid #FF9500',
              color: '#FF9500',
              padding: '0.5rem 1rem',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              fontFamily: 'inherit'
            }}
          >
            <option>IT</option>
            <option>ES</option>
            <option>EN</option>
            <option>FR</option>
            <option>DE</option>
          </select>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ 
        padding: '6rem 2rem', 
        textAlign: 'center',
        background: 'radial-gradient(circle at 50% 50%, rgba(255, 149, 0, 0.05) 0%, transparent 70%)'
      }}>
        <h1 style={{ 
          fontSize: '3.5rem', 
          marginBottom: '1rem',
          color: '#FF9500',
          fontWeight: 'bold'
        }}>
          {t.hero.title}
        </h1>
        <p style={{ fontSize: '1.3rem', marginBottom: '2rem', opacity: 0.9 }}>
          {t.hero.subtitle}
        </p>
        <button style={{
          background: 'linear-gradient(135deg, #FF9500, #D4AF37)',
          color: '#1a2b4a',
          border: 'none',
          padding: '1rem 2.5rem',
          fontSize: '1.1rem',
          fontWeight: 'bold',
          borderRadius: '0.5rem',
          cursor: 'pointer',
          marginBottom: '3rem'
        }}>
          {t.hero.cta} <ArrowRight style={{ display: 'inline', marginLeft: '0.5rem' }} />
        </button>
      </section>

      {/* Products Section */}
      <section style={{ padding: '4rem 2rem', maxWidth: '1200px', margin: '0 auto' }}>
        <h2 style={{ 
          fontSize: '2.5rem', 
          marginBottom: '3rem', 
          textAlign: 'center',
          color: '#D4AF37'
        }}>
          {t.products.title}
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
          {[
            { key: 'azioni', icon: '📈' },
            { key: 'etf', icon: '💼' },
            { key: 'fondi', icon: '🏦' }
          ].map(item => (
            <div key={item.key} style={{
              background: 'rgba(255, 149, 0, 0.05)',
              border: '1px solid rgba(255, 149, 0, 0.2)',
              padding: '2rem',
              borderRadius: '0.5rem',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>{item.icon}</div>
              <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: '#FF9500' }}>
                {t.products[item.key].name}
              </h3>
              <p style={{ marginBottom: '1.5rem', opacity: 0.8 }}>
                {t.products[item.key].desc}
              </p>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {t.products[item.key].features.map((f, i) => (
                  <li key={i} style={{ marginBottom: '0.5rem', color: '#D4AF37' }}>
                    ✓ {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Benefits Section */}
      <section style={{ 
        padding: '4rem 2rem', 
        background: 'rgba(255, 149, 0, 0.03)',
        borderTop: '1px solid rgba(255, 149, 0, 0.1)',
        borderBottom: '1px solid rgba(255, 149, 0, 0.1)'
      }}>
        <h2 style={{ 
          fontSize: '2.5rem', 
          marginBottom: '3rem', 
          textAlign: 'center',
          color: '#D4AF37'
        }}>
          {t.benefits.title}
        </h2>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '2rem' }}>
          {t.benefits.items.map((item, i) => (
            <div key={i} style={{ padding: '1.5rem' }}>
              <div style={{ fontSize: '2rem', marginBottom: '1rem', color: '#FF9500' }}>
                {item.icon === 'Zap' && '⚡'}
                {item.icon === 'Globe' && '🌍'}
                {item.icon === 'TrendingUp' && '📈'}
                {item.icon === 'BarChart3' && '📊'}
              </div>
              <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem', color: '#FF9500' }}>
                {item.title}
              </h3>
              <p style={{ opacity: 0.8 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing Section */}
      <section style={{ padding: '4rem 2rem', maxWidth: '1200px', margin: '0 auto' }}>
        <h2 style={{ 
          fontSize: '2.5rem', 
          marginBottom: '3rem', 
          textAlign: 'center',
          color: '#D4AF37'
        }}>
          {t.pricing.title}
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem' }}>
          {[
            { name: 'azioni', data: t.pricing.azioni },
            { name: 'etf', data: t.pricing.etf },
            { name: 'fondi', data: t.pricing.fondi },
            { name: 'bundle', data: t.pricing.bundle }
          ].map(item => (
            <div key={item.name} style={{
              background: item.name === 'bundle' ? 'linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(255, 149, 0, 0.1))' : 'rgba(255, 149, 0, 0.05)',
              border: item.name === 'bundle' ? '2px solid #D4AF37' : '1px solid rgba(255, 149, 0, 0.2)',
              padding: '2rem',
              borderRadius: '0.5rem',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#FF9500', marginBottom: '0.5rem' }}>
                {item.data.price}
              </div>
              <div style={{ color: '#D4AF37', marginBottom: '1rem' }}>{item.data.period}</div>
              <div style={{ opacity: 0.9 }}>{item.data.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Demo Section */}
      <section style={{ 
        padding: '4rem 2rem', 
        background: 'rgba(255, 149, 0, 0.03)',
        borderTop: '1px solid rgba(255, 149, 0, 0.1)'
      }}>
        <h2 style={{ 
          fontSize: '2.5rem', 
          marginBottom: '1rem', 
          textAlign: 'center',
          color: '#D4AF37'
        }}>
          {t.demo.title}
        </h2>
        <p style={{ textAlign: 'center', marginBottom: '2rem', opacity: 0.8 }}>
          {t.demo.subtitle}
        </p>

        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', justifyContent: 'center' }}>
            {['azioni', 'etf', 'fondi'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: activeTab === tab ? '#FF9500' : 'rgba(255, 149, 0, 0.1)',
                  color: activeTab === tab ? '#1a2b4a' : '#FF9500',
                  border: 'none',
                  padding: '0.7rem 1.5rem',
                  borderRadius: '0.3rem',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                {t.demo.tabs[tab]}
              </button>
            ))}
          </div>

          <div style={{
            background: 'rgba(0, 0, 0, 0.3)',
            border: '1px solid rgba(255, 149, 0, 0.2)',
            borderRadius: '0.5rem',
            padding: '2rem',
            overflowX: 'auto'
          }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.9rem'
            }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255, 149, 0, 0.3)' }}>
                  {activeTab === 'azioni' && (
                    <>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Ticker</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Azienda</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>EV/FCF</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>P/B</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>ROE</th>
                    </>
                  )}
                  {activeTab === 'etf' && (
                    <>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Ticker</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Nome</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>TER</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>AUM (M€)</th>
                    </>
                  )}
                  {activeTab === 'fondi' && (
                    <>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Ticker</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>Nome</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>TER</th>
                      <th style={{ padding: '1rem', textAlign: 'left', color: '#FF9500' }}>AUM (M€)</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {(activeTab === 'azioni' ? mockData.azioni : activeTab === 'etf' ? mockData.etf : mockData.fondi).map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255, 149, 0, 0.1)' }}>
                    {activeTab === 'azioni' && (
                      <>
                        <td style={{ padding: '1rem', color: '#FF9500', fontWeight: 'bold' }}>{row.ticker}</td>
                        <td style={{ padding: '1rem' }}>{row.name}</td>
                        <td style={{ padding: '1rem' }}>{row.evfcf.toFixed(2)}</td>
                        <td style={{ padding: '1rem' }}>{row.pb.toFixed(2)}</td>
                        <td style={{ padding: '1rem', color: '#00D4FF' }}>{row.roe.toFixed(1)}%</td>
                      </>
                    )}
                    {activeTab === 'etf' && (
                      <>
                        <td style={{ padding: '1rem', color: '#FF9500', fontWeight: 'bold' }}>{row.ticker}</td>
                        <td style={{ padding: '1rem' }}>{row.name}</td>
                        <td style={{ padding: '1rem' }}>{row.ter.toFixed(2)}%</td>
                        <td style={{ padding: '1rem', color: '#00D4FF' }}>{row.aum.toLocaleString()}</td>
                      </>
                    )}
                    {activeTab === 'fondi' && (
                      <>
                        <td style={{ padding: '1rem', color: '#FF9500', fontWeight: 'bold' }}>{row.ticker}</td>
                        <td style={{ padding: '1rem' }}>{row.name}</td>
                        <td style={{ padding: '1rem' }}>{row.ter.toFixed(2)}%</td>
                        <td style={{ padding: '1rem', color: '#00D4FF' }}>{row.aum.toLocaleString()}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section style={{ 
        padding: '4rem 2rem', 
        maxWidth: '600px', 
        margin: '0 auto',
        textAlign: 'center'
      }}>
        <h2 style={{ fontSize: '2rem', marginBottom: '1rem', color: '#D4AF37' }}>
          {t.cta.title}
        </h2>
        <p style={{ marginBottom: '2rem', opacity: 0.8 }}>
          {t.cta.subtitle}
        </p>

        <form onSubmit={handleEmailSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t.cta.placeholder}
            required
            style={{
              flex: 1,
              padding: '1rem',
              background: 'rgba(255, 149, 0, 0.1)',
              border: '1px solid #FF9500',
              color: '#e8e8e8',
              borderRadius: '0.3rem',
              fontFamily: 'inherit'
            }}
          />
          <button
            type="submit"
            style={{
              background: 'linear-gradient(135deg, #FF9500, #D4AF37)',
              color: '#1a2b4a',
              border: 'none',
              padding: '1rem 2rem',
              fontWeight: 'bold',
              borderRadius: '0.3rem',
              cursor: 'pointer'
            }}
          >
            {t.cta.button}
          </button>
        </form>

        {emailSubmitted && (
          <div style={{
            marginTop: '1rem',
            padding: '1rem',
            background: 'rgba(0, 212, 255, 0.1)',
            border: '1px solid #00D4FF',
            borderRadius: '0.3rem',
            color: '#00D4FF'
          }}>
            ✓ {t.cta.success}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer style={{ 
        padding: '3rem 2rem', 
        textAlign: 'center',
        borderTop: '1px solid rgba(255, 149, 0, 0.1)',
        opacity: 0.7
      }}>
        <p>{t.footer.company}</p>
        <p style={{ marginTop: '1rem', fontSize: '0.9rem' }}>{t.footer.rights}</p>
      </footer>
    </div>
  );
};

export default RobotTraderLanding;
