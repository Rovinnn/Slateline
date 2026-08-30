(function () {
  var TOPO = 'https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json';
  var topoPromise = null;

  function waitForLibs(timeout) {
    var t0 = Date.now();
    return new Promise(function (res, rej) {
      (function poll() {
        if (window.d3 && window.topojson) return res();
        if (Date.now() - t0 > timeout) return rej(new Error('Map libraries did not load'));
        setTimeout(poll, 120);
      })();
    });
  }

  function loadTopo() {
    if (!topoPromise) {
      topoPromise = waitForLibs(12000)
        .then(function () { return fetch(TOPO); })
        .then(function (r) {
          if (!r.ok) throw new Error('Boundary data unavailable (' + r.status + ')');
          return r.json();
        })
        .then(function (topo) { return window.topojson.feature(topo, topo.objects.countries); })
        .catch(function (e) { topoPromise = null; throw e; });
    }
    return topoPromise;
  }

  var INK = '#131F25', INK2 = '#4E5A60', INK3 = '#879196', RULE = '#D8DFE3';
  var SCALE = ['#AE4538', '#AA6A00', '#606B70', '#008687'];

  function fmt(n) { return n.toLocaleString('en-US'); }

  class IncentiveMap extends HTMLElement {
    static get observedAttributes() { return ['data-payload']; }

    connectedCallback() {
      if (this._init) return;
      this._init = true;
      this.style.display = 'block';
      this.style.height = '100%';
      this.innerHTML = '<div data-shell style="height:100%;position:relative;background:#F7F5F1"></div>';
      this.shell = this.querySelector('[data-shell]');
      this.setState('loading');
      this.boot();
      this._ro = new ResizeObserver(function () { this.draw(); }.bind(this));
      this._ro.observe(this);
    }

    disconnectedCallback() { if (this._ro) this._ro.disconnect(); }

    attributeChangedCallback() { if (this._init && this.geo) this.draw(); }

    boot() {
      var self = this;
      loadTopo().then(function (geo) {
        self.geo = geo;
        self.setState('ready');
        self.draw();
      }).catch(function (e) {
        self.setState('error', e.message);
      });
    }

    payload() {
      try { return JSON.parse(this.getAttribute('data-payload') || '{}'); }
      catch (e) { return {}; }
    }

    setState(s, msg) {
      this.state = s;
      if (s === 'loading') {
        this.shell.innerHTML =
          '<div style="height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px">' +
          '<div style="width:22px;height:22px;border:2px solid ' + RULE + ';border-top-color:' + INK2 + ';border-radius:50%;animation:iv-spin .8s linear infinite"></div>' +
          '<div style="font:500 12px/1.4 \'IBM Plex Mono\',monospace;letter-spacing:.04em;color:' + INK2 + '">LOADING BOUNDARY DATA</div>' +
          '<div style="font:400 12px/1.4 \'IBM Plex Mono\',monospace;color:' + INK3 + '">world-atlas 2.0.2 · Natural Earth</div></div>';
      } else if (s === 'error') {
        this.shell.innerHTML =
          '<div style="height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:32px;text-align:center">' +
          '<div style="font:600 14px/1.4 \'Public Sans\',sans-serif;color:#AE4538">Map could not be drawn</div>' +
          '<div style="font:400 13px/1.5 \'Public Sans\',sans-serif;color:' + INK2 + ';max-width:340px">' + (msg || 'Unknown error') +
          '. Jurisdiction rankings on the Memo tab are unaffected — the map is a supporting view only.</div>' +
          '<button data-retry style="margin-top:4px;font:500 12px/1 \'IBM Plex Mono\',monospace;letter-spacing:.04em;padding:9px 14px;background:#fff;border:1px solid ' + INK + ';color:' + INK + ';cursor:pointer">RETRY</button></div>';
        var b = this.shell.querySelector('[data-retry]');
        var self = this;
        if (b) b.onclick = function () { self.setState('loading'); self.boot(); };
      }
    }

    draw() {
      if (this.state !== 'ready' || !this.geo) return;
      var p = this.payload();
      var pts = (p.points || []);
      var home = p.homeBase;
      var w = this.clientWidth || 900, h = this.clientHeight || 600;
      if (!pts.length || !home || w < 60 || h < 60) return;

      var d3 = window.d3;
      var coords = pts.map(function (d) { return [d.lon, d.lat]; }).concat([[home.lon, home.lat]]);
      var lons = coords.map(function (c) { return c[0]; }), lats = coords.map(function (c) { return c[1]; });
      var pad = 7;
      var box = { type: 'MultiPoint', coordinates: [[Math.min.apply(null, lons) - pad, Math.min.apply(null, lats) - pad], [Math.max.apply(null, lons) + pad, Math.max.apply(null, lats) + pad]] };
      var proj = d3.geoMercator().fitExtent([[28, 28], [w - 28, h - 66]], box);
      var path = d3.geoPath(proj);

      var nets = pts.filter(function (d) { return !d.excluded; }).map(function (d) { return d.net; });
      var lo = Math.min.apply(null, nets), hi = Math.max.apply(null, nets);
      var color = d3.scaleLinear().domain([lo, lo + (hi - lo) / 3, lo + 2 * (hi - lo) / 3, hi]).range(SCALE).clamp(true);

      this.shell.innerHTML = '';
      var svg = d3.select(this.shell).append('svg')
        .attr('width', w).attr('height', h)
        .style('display', 'block').style('background', '#F7F5F1');

      svg.append('g').selectAll('path').data(this.geo.features).join('path')
        .attr('d', path).attr('fill', '#F0EEEA').attr('stroke', '#DDDBD4').attr('stroke-width', 0.7);

      var hp = proj([home.lon, home.lat]);

      svg.append('g').selectAll('path').data(pts).join('path')
        .attr('d', function (d) { return path({ type: 'LineString', coordinates: [[home.lon, home.lat], [d.lon, d.lat]] }); })
        .attr('fill', 'none')
        .attr('stroke', function (d) { return d.excluded ? '#C0BDB6' : color(d.net); })
        .attr('stroke-width', function (d) { return d.rank === 1 ? 1.6 : 1; })
        .attr('stroke-dasharray', function (d) { return d.rank === 1 ? null : '3 3'; })
        .attr('opacity', function (d) { return d.excluded ? 0.5 : 0.75; });

      var placed = [];
      pts.forEach(function (d) {
        var q = proj([d.lon, d.lat]);
        d._dodge = 0;
        for (var k = 0; k < placed.length; k++) {
          if (Math.abs(placed[k][0] - q[0]) < 78 && Math.abs((placed[k][1] + placed[k][2]) - (q[1] + d._dodge)) < 15) {
            d._dodge += 17; k = -1;
          }
        }
        placed.push([q[0], q[1], d._dodge]);
      });

      var g = svg.append('g').selectAll('g').data(pts).join('g')
        .attr('transform', function (d) { var q = proj([d.lon, d.lat]); return 'translate(' + q[0] + ',' + q[1] + ')'; })
        .style('cursor', 'default');

      g.append('circle')
        .attr('r', function (d) { return d.excluded ? 5 : (d.rank === 1 ? 9 : 7); })
        .attr('fill', function (d) { return d.excluded ? '#F7F5F1' : color(d.net); })
        .attr('stroke', function (d) { return d.excluded ? '#A7A49C' : '#F7F5F1'; })
        .attr('stroke-width', 1.6);

      g.filter(function (d) { return d.rank === 1; }).append('circle')
        .attr('r', 14).attr('fill', 'none').attr('stroke', function (d) { return color(d.net); }).attr('stroke-width', 1).attr('opacity', 0.5);

      g.append('text')
        .attr('x', 0).attr('y', function (d) { return (d.rank === 1 ? -20 : -12) - (d._dodge || 0); })
        .attr('text-anchor', 'middle')
        .style('font', function (d) { return (d.rank === 1 ? '600' : '500') + ' 11.5px "Public Sans",sans-serif'; })
        .style('fill', INK).text(function (d) { return d.name; });

      g.append('text')
        .attr('x', 0).attr('y', function (d) { return (d.rank === 1 ? 26 : 22); })
        .attr('text-anchor', 'middle')
        .style('font', '500 11px "IBM Plex Mono",monospace')
        .style('fill', function (d) { return d.excluded ? INK3 : INK2; })
        .text(function (d) { return d.excluded ? 'excluded' : d.netLabel; });

      g.append('title').text(function (d) {
        return d.name + ' — ' + d.hub + '\n' + (d.excluded ? 'Excluded: ' + d.reason : 'Net benefit ' + d.netLabel + ' · ' + fmt(Math.round(d.km)) + ' km from ' + home.name);
      });

      var hg = svg.append('g').attr('transform', 'translate(' + hp[0] + ',' + hp[1] + ')');
      hg.append('rect').attr('x', -6).attr('y', -6).attr('width', 12).attr('height', 12)
        .attr('fill', '#F7F5F1').attr('stroke', INK).attr('stroke-width', 2).attr('transform', 'rotate(45)');
      hg.append('text').attr('y', -16).attr('text-anchor', 'middle')
        .style('font', '600 11.5px "Public Sans",sans-serif').style('fill', INK).text(home.name);
      hg.append('text').attr('y', 24).attr('text-anchor', 'middle')
        .style('font', '500 10.5px "IBM Plex Mono",monospace').style('letter-spacing', '.06em').style('fill', INK2).text('HOME BASE');

      var lg = svg.append('g').attr('transform', 'translate(28,' + (h - 30) + ')');
      lg.append('text').style('font', '500 10.5px "IBM Plex Mono",monospace').style('letter-spacing', '.06em').style('fill', INK2)
        .attr('y', -12).text('NET BENEFIT AFTER RELOCATION');
      SCALE.forEach(function (c, i) {
        lg.append('rect').attr('x', i * 26).attr('y', 0).attr('width', 26).attr('height', 7).attr('fill', c);
      });
      lg.append('text').attr('x', 0).attr('y', 21).style('font', '400 10.5px "IBM Plex Mono",monospace').style('fill', INK3).text('lower');
      lg.append('text').attr('x', 104).attr('y', 21).attr('text-anchor', 'end').style('font', '400 10.5px "IBM Plex Mono",monospace').style('fill', INK3).text('higher');
      lg.append('text').attr('x', 132).attr('y', 6).style('font', '400 11px "IBM Plex Mono",monospace').style('fill', INK3)
        .text('○ hollow = fails an active constraint · dashed line = runner-up');
    }
  }

  if (!customElements.get('incentive-map')) customElements.define('incentive-map', IncentiveMap);
})();
