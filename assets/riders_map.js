// Funções JavaScript de customização das camadas GeoJSON no Dash-Leaflet
window.ifeed = Object.assign({}, window.ifeed, {
    // Renderiza cada cluster de restaurantes com classes de estilo e tooltip informativa
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

    // Renderiza cada cluster de entregadores como um ícone em formato de losango
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

    // Renderiza entregadores individuais (quando desagrupados no zoom) como círculos laranjas
    riderPointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            radius: 6,
            color: "#ffffff",
            fillColor: "#ff6b00",
            fillOpacity: 0.9,
            weight: 1.5
        });
    }
});
