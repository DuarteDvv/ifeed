// funções JavaScript de customização das camadas GeoJSON no Dash-Leaflet
window.ifeed = Object.assign({}, window.ifeed, {
    // renderiza cada cluster de restaurantes com classes de estilo e tooltip informativa
    barClusterToLayer: function (feature, latlng) {
        var count = feature.properties.point_count;
        var countLabel = feature.properties.point_count_abbreviated;

        var className = "marker-cluster marker-cluster-small";
        if (count >= 1000) {
            className = "marker-cluster marker-cluster-large";
        } else if (count >= 100) {
            className = "marker-cluster marker-cluster-medium";
        }

        var icon = L.divIcon({
            html: "<div><span>" + countLabel + "</span></div>",
            className: className,
            iconSize: L.point(40, 40)
        });

        var marker = L.marker(latlng, { icon: icon });
        var label = count === 1 ? "1 restaurante nesta região" : count.toLocaleString("pt-BR") + " restaurantes nesta região";
        marker.bindTooltip(label, { direction: "right", offset: [20, 0] });
        return marker;
    },

    // renderiza cada cluster de entregadores como um ícone em formato de losango
    riderClusterToLayer: function (feature, latlng) {
        var count = feature.properties.point_count;
        var countLabel = feature.properties.point_count_abbreviated;

        var sizeClass = "rider-cluster-small";
        if (count >= 500) {
            sizeClass = "rider-cluster-large";
        } else if (count >= 50) {
            sizeClass = "rider-cluster-medium";
        }

        var icon = L.divIcon({
            html: '<div class="rider-cluster-diamond"><span>' + countLabel + '</span></div>',
            className: "rider-cluster " + sizeClass,
            iconSize: L.point(44, 44)
        });

        var marker = L.marker(latlng, { icon: icon });
        var label = count === 1 ? "1 entregador nesta região" : count.toLocaleString("pt-BR") + " entregadores nesta região";
        marker.bindTooltip(label, { direction: "right", offset: [22, 0] });
        return marker;
    },

    // renderiza cada cluster de entregadores descartados como um ícone em formato de losango cinza
    riderDiscardedClusterToLayer: function (feature, latlng) {
        var count = feature.properties.point_count;
        var countLabel = feature.properties.point_count_abbreviated;

        var sizeClass = "rider-cluster-small";
        if (count >= 500) {
            sizeClass = "rider-cluster-large";
        } else if (count >= 50) {
            sizeClass = "rider-cluster-medium";
        }

        var icon = L.divIcon({
            html: '<div class="rider-cluster-diamond"><span>' + countLabel + '</span></div>',
            className: "rider-cluster rider-cluster-discarded " + sizeClass,
            iconSize: L.point(44, 44)
        });

        var marker = L.marker(latlng, { icon: icon });
        var label = count === 1 ? "1 entregador descartado nesta região" : count.toLocaleString("pt-BR") + " entregadores descartados nesta região";
        marker.bindTooltip(label, { direction: "right", offset: [22, 0] });
        return marker;
    },

    // renderiza entregadores individuais: em destaque (laranja) quando filtrados e em cinza quando descartados
    riderPointToLayer: function (feature, latlng) {
        var props = (feature && feature.properties) ? feature.properties : {};
        var status = props.status || "normal";
        var marker;

        if (status === "discarded") {
            marker = L.circleMarker(latlng, {
                radius: 5,
                color: "#d5d8dc",
                fillColor: "#808b96",
                fillOpacity: 0.55,
                weight: 1.0
            });
        } else if (status === "filtered") {
            marker = L.circleMarker(latlng, {
                radius: 7,
                color: "#ffffff",
                fillColor: "#ff6b00",
                fillOpacity: 0.95,
                weight: 2.0
            });
        } else {
            marker = L.circleMarker(latlng, {
                radius: 6,
                color: "#ffffff",
                fillColor: "#ff6b00",
                fillOpacity: 0.9,
                weight: 1.5
            });
        }

        // construção dinâmica de tooltip e popup a partir de dados numéricos primitivos
        var formatDist = function (m) {
            if (m === null || m === undefined) return null;
            return m < 1000 ? Math.round(m) + " m" : (m / 1000).toFixed(2) + " km (" + Math.round(m) + " m)";
        };

        var formatTime = function (min) {
            if (min === null || min === undefined) return null;
            if (min < 1.0) {
                var s = Math.round(min * 60);
                return (s > 0 ? s : "< 1") + " s";
            }
            var mPart = Math.floor(min);
            var sPart = Math.round((min - mPart) * 60);
            return sPart > 0 ? mPart + " min " + sPart + " s" : mPart + " min";
        };

        var lat = latlng.lat.toFixed(6);
        var lng = latlng.lng.toFixed(6);
        var id = props.id;
        var geohash = props.geohash || "N/A";
        var distVal = props.dist !== undefined ? props.dist : props.distance;
        var roadDistVal = props.road_dist !== undefined ? props.road_dist : props.road_distance;
        var timeVal = props.time !== undefined ? props.time : props.estimated_time;

        var tooltipText = "Entregador #" + id;
        var popupHtml = "";

        if (status === "filtered") {
            var distStr = formatDist(distVal);
            var timeStr = formatTime(timeVal);
            var roadDistStr = formatDist(roadDistVal);

            if (props.ranking_by === "time" && timeStr) {
                tooltipText = "Entregador #" + id + " — " + timeStr;
            } else if (distStr) {
                tooltipText = "Entregador #" + id + " — " + distStr;
            }

            popupHtml = "<b>Entregador #" + id + "</b> <span style='color:#ff6b00;font-weight:bold;'>(Dentro do raio)</span><br>";
            if (timeStr) popupHtml += "<b>Tempo de trajeto (ruas):</b> " + timeStr + "<br>";
            if (roadDistStr) popupHtml += "<b>Distância pelas ruas:</b> " + roadDistStr + "<br>";
            if (distStr) popupHtml += "<b>Distância em linha reta:</b> " + distStr + "<br>";
            popupHtml += "<b>Coordenadas:</b> (" + lat + ", " + lng + ")<br>";
            popupHtml += "<b>Geohash:</b> " + geohash;
        } else if (status === "discarded") {
            var distInfo = formatDist(distVal) || "Fora da região";
            tooltipText = "Entregador #" + id + " (Descartado — " + distInfo + ")";
            popupHtml = "<b>Entregador #" + id + "</b> <span style='color:#808b96;font-weight:bold;'>(Descartado)</span><br>" +
                "<b>Distância ao restaurante:</b> " + distInfo + "<br>" +
                "<b>Coordenadas:</b> (" + lat + ", " + lng + ")<br>" +
                "<b>Geohash:</b> " + geohash;
        } else {
            popupHtml = "<b>Entregador #" + id + "</b><br>" +
                "<b>Coordenadas:</b> (" + lat + ", " + lng + ")<br>" +
                "<b>Geohash:</b> " + geohash;
        }

        marker.bindTooltip(tooltipText);
        marker.bindPopup(popupHtml);
        return marker;
    }
});
