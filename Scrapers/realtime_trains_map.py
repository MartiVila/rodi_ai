from flask import Flask, jsonify, render_template_string, Response
import threading
import time
import os
import json

app = Flask(__name__)

latest_trains = {
    "timestamp": None,
    "trains": [],
}

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
LATEST_TRAINS_FILE = os.path.join(DATA_DIR, 'latest_trains.json')

def poll_trains(poll_interval=5):
    global latest_trains
    while True:
        try:
            if os.path.exists(LATEST_TRAINS_FILE):
                with open(LATEST_TRAINS_FILE, 'r', encoding='utf-8') as fh:
                    obj = json.load(fh)
                    # Validacio basica de l'estructura
                    trains = obj.get('trains', []) if isinstance(obj, dict) else []
                    
                    cleaned = []
                    for t in trains:
                        try:
                            cleaned.append({
                                'id': str(t.get('id')),
                                'trip': str(t.get('trip', '')),
                                'origin': t.get('origin'),
                                'destination': t.get('destination'),
                                'lat': float(t.get('lat')),
                                'lon': float(t.get('lon')),
                                'speed': t.get('speed'),
                                'status': t.get('status'),
                            })
                        except Exception:
                            continue
                    latest_trains['timestamp'] = int(time.time())
                    latest_trains['trains'] = cleaned
                    app.logger.info(f"Loaded {len(cleaned)} trains from {LATEST_TRAINS_FILE}")
            else:
                latest_trains['trains'] = []
        except Exception as e:
            app.logger.exception('Error reading latest trains file')
        time.sleep(poll_interval)


@app.route('/debug/raw')
def debug_raw():
  if os.path.exists(LATEST_TRAINS_FILE):
    try:
      with open(LATEST_TRAINS_FILE, 'r', encoding='utf-8') as fh:
        return Response(fh.read(), mimetype='text/plain')
    except Exception as e:
      return Response(f'Error reading file: {e}', status=500, mimetype='text/plain')
  return Response('latest_trains.json not found', status=404, mimetype='text/plain')


@app.route('/debug/json')
def debug_json():
  """Tornem el JSON parsejat del fitxer latest_trains per a depuració."""
  if os.path.exists(LATEST_TRAINS_FILE):
    try:
      with open(LATEST_TRAINS_FILE, 'r', encoding='utf-8') as fh:
        obj = json.load(fh)
        return jsonify(obj)
    except Exception as e:
      return jsonify({'error': 'read_failed', 'detail': str(e)}), 500
  return jsonify({'error': 'not_found'}), 404


@app.route("/trains")
def trains_endpoint():
    """Tornem els trens en format JSON per al mapa en temps real."""
    try:
        return jsonify(latest_trains)
    except Exception as e:
        app.logger.exception("Error serializing latest_trains")
        return jsonify({"timestamp": int(time.time()), "trains": [], "error": "serialization_failed", "detail": str(e)}), 500

# Injeccio de JS i HTML per al mapa
INDEX_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trenes en tiempo real - Mapa</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
      #map { position: absolute; top: 0; bottom: 0; right: 0; left: 0; }
      .train-marker { font-weight: bold; }
    </style>
  </head>
  <body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
      const map = L.map('map').setView([41.5, 1.8], 8); // center on Catalunya

      // Base layers
      const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(map);
      const carto = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', { attribution: '© CartoDB' });

      // OpenRailwayMap overlay
      const orm = L.tileLayer('https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png', { attribution: 'OpenRailwayMap' }).addTo(map);

      const layersControl = L.control.layers({ 'OpenStreetMap': osm, 'CartoDB': carto }, { 'OpenRailwayMap': orm }).addTo(map);

  // markers by train id
  const markers = {};
  let firstLoad = true;
  let autoFit = true; // when true, map will fit bounds to markers after updates
  let followId = null; // id of train to follow (centers map on this train each update)

      // determine if a train should be considered delayed
      function isDelayed(raw) {
        if (!raw) return false;
        if (typeof raw.delay !== 'undefined' && Number(raw.delay)) {
          try { return Number(raw.delay) > 0; } catch(e) { }
        }
        const s = (raw.status || '').toString().toLowerCase();
        if (s.includes('delay') || s.includes('delayed') || s.includes('late')) return true;
        if (s.includes('retras') || s.includes('retraso')) return true;
        return false;
      }

      async function fetchTrains(){
        try{
          const resp = await fetch('/trains');
          const ct = resp.headers.get('content-type') || '';
          let data;
          if (ct.includes('application/json')) {
            data = await resp.json();
          } else {
            // If the server returned HTML or text (debug page / error), log it for debugging
            const txt = await resp.text();
            console.error('Unexpected /trains response (not JSON):', txt);
            return;
          }

          // Defensive checks
          if (!data || !Array.isArray(data.trains)) {
            console.warn('No trains array in /trains response', data);
            return;
          }

          // data.trains is array of {id, lat, lon, trip, status}
          const newIds = new Set();
          const bounds = [];
          for(const raw of data.trains){
            try {
              // normalize id as string
              const id = String(raw.id);
              const lat = Number(raw.lat);
              const lon = Number(raw.lon);

              // skip invalid coordinates
              if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
                console.warn('Skipping train with invalid coords', raw);
                continue;
              }

              newIds.add(id);
              bounds.push([lat, lon]);

              if (markers[id]){
                // move marker
                markers[id].setLatLng([lat, lon]);
                markers[id].setPopupContent(`<b>${id}</b><br>${raw.trip || ''}<br>${raw.status || ''}`);
                // update style if delay status changes
                try {
                  const delayed = isDelayed(raw);
                  const color = delayed ? 'red' : 'green';
                  const fill = delayed ? '#f03' : '#3f3';
                  if (typeof markers[id].setStyle === 'function') {
                    markers[id].setStyle({ color: color, fillColor: fill });
                  }
                } catch(e){ /* ignore style update errors */ }
              } else {
                const m = makeMarker(lat, lon, id, raw);
                markers[id] = m;
              }
            } catch(inner){
              console.error('Error processing train entry', raw, inner);
              continue;
            }
          }

          // remove markers not present
          for(const id of Object.keys(markers)){
            if(!newIds.has(id)){
              try {
                map.removeLayer(markers[id]);
              } catch(e){ /* ignore */ }
              delete markers[id];
            }
          }

          // Fit map to markers on first load or when autoFit is enabled
          if (bounds.length > 0) {
            try {
              const leafletBounds = L.latLngBounds(bounds);
              if (firstLoad || autoFit) {
                map.fitBounds(leafletBounds, {padding: [50, 50]});
              }
            } catch(e){ console.warn('fitBounds failed', e); }
          }

          // If following a specific train, center map on that marker (preserve zoom)
          if (followId && markers[followId]) {
            try {
              const latlng = markers[followId].getLatLng();
              map.panTo(latlng);
            } catch(e){ console.warn('panTo failed', e); }
          }

          firstLoad = false;

        }catch(e){
          console.error('Error fetching trains', e);
        }
      }

      // Simple control to toggle auto-fit behaviour
      const AutoFitControl = L.Control.extend({
        onAdd: function(map) {
          const container = L.DomUtil.create('div', 'leaflet-bar');
          container.style.background = 'white';
          container.style.padding = '4px';
          const label = L.DomUtil.create('label', '', container);
          label.innerHTML = '<input id="autofit_chk" type="checkbox" checked /> Auto-fit';
          L.DomEvent.disableClickPropagation(container);
          return container;
        }
      });
      map.addControl(new AutoFitControl({ position: 'topright' }));

      // wire autofit checkbox
      document.addEventListener('DOMContentLoaded', ()=>{
        const chk = document.getElementById('autofit_chk');
        if (chk) {
          chk.addEventListener('change', (e)=>{
            autoFit = !!e.target.checked;
          });
        }
      });

      // allow clicking a marker to follow that train (center on it each update)
      function makeMarker(lat, lon, id, raw) {
        const delayed = isDelayed(raw);
        const color = delayed ? 'red' : 'green';
        const fill = delayed ? '#f03' : '#3f3';
        const m = L.circleMarker([lat, lon], {radius:6, color: color, fillColor: fill, fillOpacity: 0.7});
        m.addTo(map);
        const delayInfo = (typeof raw.delay !== 'undefined') ? `<br><b>Delay:</b> ${raw.delay}` : '';
        m.bindPopup(`<b>${id}</b><br>${raw.trip || ''}<br>${raw.status || ''}${delayInfo}<br><small>Click to follow</small>`);
        m.on('click', ()=>{
          followId = id;
          map.panTo([lat, lon]);
        });
        return m;
      }

      // clicking map background clears follow mode
      map.on('click', ()=>{ followId = null; });

      // initial fetch and interval
      fetchTrains();
      setInterval(fetchTrains, 10000);
    </script>
  </body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(INDEX_HTML)


def start_background_poller():
    t = threading.Thread(target=poll_trains, args=(10,), daemon=True)
    t.start()


if __name__ == '__main__':
    start_background_poller()
    app.run(host='0.0.0.0', port=5000, debug=True)
