from flask import Flask, jsonify, render_template_string, Response
import threading
import time
import os
import json

app = Flask(__name__)

# Shared storage for latest trains
latest_trains = {
    "timestamp": None,
    "trains": [],
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LATEST_TRAINS_FILE = os.path.join(DATA_DIR, "latest_trains.json")

# We will NOT call the remote API from this map server. Instead we read the
# local JSON file produced by `scraper_directe.py` (write_trains_to_file).
# Ensure scraper_directe is running in a separate process and writing updates.


def poll_trains(poll_interval=5):
    """Background thread: read the latest_trains.json file periodically and store it in memory.

    NOTE: This intentionally does NOT call the remote API. Run `scraper_directe.py` in a
    separate process to produce `data/latest_trains.json` using write_trains_to_file.
    """
    global latest_trains
    while True:
        try:
            if os.path.exists(LATEST_TRAINS_FILE):
                with open(LATEST_TRAINS_FILE, 'r', encoding='utf-8') as fh:
                    obj = json.load(fh)
                    # Basic validation
                    trains = obj.get('trains', []) if isinstance(obj, dict) else []
                    # Ensure fields are correct types
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
                # no file yet; keep previous data but zero trains
                latest_trains['trains'] = []
        except Exception as e:
            app.logger.exception('Error reading latest trains file')
        time.sleep(poll_interval)


@app.route('/debug/raw')
def debug_raw():
  """Return raw file contents for debugging (text)."""
  if os.path.exists(LATEST_TRAINS_FILE):
    try:
      with open(LATEST_TRAINS_FILE, 'r', encoding='utf-8') as fh:
        return Response(fh.read(), mimetype='text/plain')
    except Exception as e:
      return Response(f'Error reading file: {e}', status=500, mimetype='text/plain')
  return Response('latest_trains.json not found', status=404, mimetype='text/plain')


@app.route('/debug/json')
def debug_json():
  """Return parsed JSON from the latest_trains file for debugging."""
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
    """Return latest trains as JSON."""
    try:
        # Ensure we always return a JSON object even if internal state contains
        # non-serializable values. jsonify will raise if something breaks; catch
        # and return a safe error object instead.
        return jsonify(latest_trains)
    except Exception as e:
        app.logger.exception("Error serializing latest_trains")
        return jsonify({"timestamp": int(time.time()), "trains": [], "error": "serialization_failed", "detail": str(e)}), 500


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
        const m = L.circleMarker([lat, lon], {radius:6, color: 'red', fillColor: '#f03', fillOpacity: 0.7});
        m.addTo(map);
        m.bindPopup(`<b>${id}</b><br>${raw.trip || ''}<br>${raw.status || ''}<br><small>Click to follow</small>`);
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
