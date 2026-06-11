"""CSS styles for the model comparison HTML report.

Extracted to its own module for SRP compliance. Matches the Clinical Indigo
design system (dark navy theme) used across the EpiForecast-MX site.
"""

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --burgundy:#F472B6;--dark-burgundy:#8E2A63;--teal:#5B8DEF;--dark-teal:#16203A;
  --gold:#2DD4BF;--cream:#E7ECF5;--cream-light:#1C2740;--cream-pale:#131C30;
  --cool-gray:#9FB0CE;--neutral-black:#E7ECF5;
  --burgundy-light:#F472B6;--teal-light:#5B8DEF;--gold-light:#2DD4BF;
  --orange:#FF6F00;--indigo:#1A237E;
  --font-display:'DM Serif Display',Georgia,serif;
  --font-body:'Source Sans 3','Source Sans Pro',sans-serif;
  --font-mono:'JetBrains Mono','Fira Code',monospace;
  --shadow-sm:0 2px 8px rgba(0,0,0,.30);--shadow-md:0 8px 24px rgba(0,0,0,.35);
  --shadow-lg:0 16px 48px rgba(0,0,0,.45);--radius:16px;--radius-sm:10px;
}
body{font-family:var(--font-body);background:var(--cream-pale);color:var(--neutral-black);
  line-height:1.7;-webkit-font-smoothing:antialiased}
body::before{content:'';position:fixed;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity:.025;pointer-events:none;z-index:0}

.container{max-width:1200px;margin:0 auto;padding:0 2rem;position:relative;z-index:1}
section{padding:4rem 0}
.section-title{font-family:var(--font-display);font-size:clamp(1.8rem,4vw,2.5rem);
  margin-bottom:.5rem;color:var(--teal)}
.section-sub{color:var(--cool-gray);font-size:1rem;margin-bottom:2.5rem}

.hero{padding:7rem 2rem 5rem;text-align:center;
  background:linear-gradient(170deg,#0E1424 0%,var(--dark-teal) 60%,rgba(28,39,64,.95) 100%);
  color:var(--cream);position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 800px 600px at 30% 20%,rgba(91,141,239,.18),transparent),
  radial-gradient(ellipse 600px 500px at 70% 80%,rgba(244,114,182,.12),transparent);pointer-events:none}
.hero h1{font-family:var(--font-display);font-size:clamp(2.2rem,5vw,3.5rem);line-height:1.15;
  margin-bottom:.75rem;position:relative}
.hero .subtitle{font-size:clamp(.95rem,1.8vw,1.15rem);opacity:.8;font-weight:300;
  margin-bottom:2.5rem;position:relative}
.hero-kpis{display:flex;justify-content:center;gap:1.5rem;flex-wrap:wrap;position:relative}
.hero-kpi{background:rgba(255,255,255,.06);border:1px solid rgba(159,176,206,.18);
  border-radius:var(--radius);padding:1.5rem 2rem;backdrop-filter:blur(8px);min-width:160px;
  transition:transform .3s,box-shadow .3s}
.hero-kpi:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.4)}
.hero-kpi .value{font-family:var(--font-display);font-size:2.5rem;display:block;
  background:linear-gradient(135deg,var(--cream),var(--gold-light));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero-kpi .label{font-size:.8rem;text-transform:uppercase;letter-spacing:1px;opacity:.7}

.card{background:var(--cream-light);border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow-md);
  border:1px solid #243150;transition:transform .3s,box-shadow .3s;margin-bottom:2rem}
.card:hover{transform:translateY(-3px);box-shadow:var(--shadow-lg)}
.card h2{font-family:var(--font-display);font-size:1.5rem;margin-bottom:1rem;
  padding-bottom:.75rem;border-bottom:2px solid #243150;color:var(--teal)}
.card h3{font-size:1rem;margin:1.5rem 0 .75rem;color:var(--cool-gray);
  text-transform:uppercase;letter-spacing:.5px;font-weight:600}

.table-wrapper{overflow-x:auto;margin-top:.5rem}
table{width:100%;border-collapse:collapse;font-size:.88rem}
thead th{padding:.85rem 1rem;text-align:center;font-weight:600;text-transform:uppercase;
  font-size:.72rem;letter-spacing:.5px;color:var(--cool-gray);
  border-bottom:2px solid #243150;white-space:nowrap;
  position:sticky;top:0;background:var(--cream-light);z-index:2}
td:first-child,th:first-child{text-align:left}
tbody td{padding:.7rem 1rem;border-bottom:1px solid #243150;vertical-align:middle;
  font-family:var(--font-mono);font-size:.82rem}
tbody td:first-child,tbody td:nth-child(2){font-family:var(--font-body);font-size:.88rem}
tbody tr{transition:background .15s}
tbody tr:hover{background:#0E1424}

.c-prophet{color:var(--teal);font-weight:600}
.c-deepar{color:var(--burgundy);font-weight:600}
.c-ensemble{color:var(--orange);font-weight:600}
.c-stacking{color:#7986CB;font-weight:600}

.winner{background:rgba(13,148,136,.22) !important;font-weight:700}

.prod-badge,.diag-badge{display:inline-flex;align-items:center;gap:.35rem;padding:.25rem .85rem;
  border-radius:100px;font-family:var(--font-body);font-size:.78rem;font-weight:700;color:#fff}
.badge-green{background:#0D9488;color:#0B0F1A}
.badge-yellow{background:#F59E0B;color:#0B0F1A}
.badge-red{background:#EF4444}
.prod-prophet{background:#5B8DEF}
.prod-deepar{background:#BE185D}
.prod-ensemble{background:#FF6F00}
.prod-stacking{background:#1A237E}

.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;
  margin-top:1rem}
.thumbs a{display:block;border:1px solid #243150;border-radius:var(--radius-sm);
  overflow:hidden;transition:transform .3s,box-shadow .3s;text-decoration:none}
.thumbs a:hover{transform:translateY(-3px);box-shadow:var(--shadow-lg)}
.thumbs img{width:100%;height:auto;display:block}
.thumbs .caption{padding:.5rem .75rem;font-size:.78rem;color:var(--cool-gray);
  text-align:center;background:var(--cream-light);font-weight:500}

.reveal.animate{opacity:0;transform:translateY(30px);transition:opacity .6s ease,transform .6s ease}
.reveal.visible{opacity:1;transform:translateY(0)}

footer{background:#0E1424;color:rgba(231,236,245,.7);padding:3rem 2rem;
  text-align:center;font-size:.85rem;position:relative;z-index:1;margin-top:3rem}
footer .footer-title{font-family:var(--font-display);color:var(--cream);font-size:1.2rem;
  margin-bottom:.5rem}
footer a{color:var(--gold-light);text-decoration:none}
footer a:hover{color:var(--cream)}

@media(max-width:768px){
  .hero{padding:5rem 1.5rem 3rem}.hero-kpis{gap:.75rem}
  .hero-kpi{min-width:130px;padding:1rem 1.25rem}.hero-kpi .value{font-size:1.8rem}
  .thumbs{grid-template-columns:1fr}section{padding:2.5rem 0}.container{padding:0 1rem}
}
"""
