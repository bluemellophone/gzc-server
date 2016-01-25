function submit_cookie(name, value) {
  $.ajax({
      url: "/ajax/cookie?name=" + name + "&value=" + value,
      success: function(response){
        console.log("COOKIE: " + response);
      },
      error: function(response){
        console.log("COOKIE: " + response);
      }
  });
}

String.prototype.format = function() {
  var str = this;
  for (var i = 0; i < arguments.length; i++) {
    var reg = new RegExp("\\{" + i + "\\}", "gm");
    str = str.replace(reg, arguments[i]);
  }
  return str;
}

function undef(value, def)
{
    return ( typeof value !== 'undefined' ? value : def );
}

function removeValueFromArray(value, array)
{
    var index = array.indexOf(value);
    removeIndexFromArray(index, array)
    return index
}
function removeIndexFromArray(index, array)
{
    if (index > -1) {
        array.splice(index, 1);
    }
}

function submitPDF(car, person)
{
    var documents = {};
    $('.printarea-document').each(function( index, element ) {
        console.log("PROCESSING PRINTAREA");
        documents['head_content'] = $('head').html();
        documents['html_content'] = $(element).html();
    });

    if(Object.keys(documents).length > 0)
    {
        console.log("SENDING");
        $.ajax({
            type: "POST",
            url: '/render/' + car + '/' + person,
            data: documents,
        })
        .done(function(response) {
            console.log("SENT");
        })
        .fail(function(response) {
            console.log("ERROR");
        });
    }
}


function loadGPSMap(track, markers, center)
{
    var gps;
    var styles = [
        {
            featureType: "poi.business",
            // featureType: "poi",
            elementType: "labels",
            stylers: [
                  { visibility: "off" }
            ]
        }
    ];

    if(typeof center === 'undefined')
    {
        var min_lat = undefined;
        var max_lat = undefined;
        var min_lon = undefined;
        var max_lon = undefined;
        for (var index in track)
        {
            marker = track[index];
            console.log(marker);
            lat = marker[0];
            lon = marker[1];
            min_lat = Math.min(lat, undef(min_lat, lat));
            max_lat = Math.max(lat, undef(max_lat, lat));
            min_lon = Math.min(lon, undef(min_lon, lon));
            max_lon = Math.max(lon, undef(max_lon, lon));
        }

        lat = (max_lat + min_lat) * 0.5;
        lon = (max_lon + min_lon) * 0.5;
        center = new google.maps.LatLng(lat, lon);
        console.log("Auto Center: Lat " + lat +", Lon " + lon);
    }

    // Initialize the Google Maps API v3
    var map = new google.maps.Map(document.getElementById('gps-map-canvas'), {
        zoom: 13,
        center: center,
        // mapTypeId: google.maps.MapTypeId.HYBRID,
        // mapTypeId: google.maps.MapTypeId.ROADMAP,
        // mapTypeId: google.maps.MapTypeId.SATELLITE,
        mapTypeId: google.maps.MapTypeId.TERRAIN,
        disableDefaultUI: true,
        scrollwheel: false,
        draggable: false,
        styles: styles,
    });

    google.maps.event.addListener(map, 'bounds_changed', function() {
        bounds = map.getBounds();
        console.log("Bounds:      " + JSON.stringify(bounds))
        // console.log("Bottom Left: " + bounds['Ca']);
        // console.log("Top Right:   " + bounds['va']);
    });


    var last = undefined;
    for (var index in track)
    {
        marker = track[index];
        gps = new google.maps.LatLng(marker[0], marker[1]);
        if(last !== undefined)
        {
            if(insidePoly(undefined, [marker[1], marker[0]]))
                color = "#428BCA";
            else
                color = "#FF0000";
            new google.maps.Polyline({
                path: [last, gps],
                strokeColor: color,
                strokeOpacity: 1.0,
                strokeWeight: 2,
                map: map
            });
        }
        last = gps;
    }

    for (var index in markers)
    {
        marker = markers[index];
        gps = new google.maps.LatLng(marker[0], marker[1]);
        number = parseInt(index) + 1;
        new google.maps.Marker({
            icon: {
                // url: 'http://mt.google.com/vt/icon/name=icons/spotlight/spotlight-waypoint-a.png&color=ff004C13&psize=25&ay=50&text=•'
                // url: 'http://mt.google.com/vt/icon/name=icons/spotlight/spotlight-waypoint-b.png&color=ff004C13&psize=16&ay=48&text=A'
                url: 'http://mt.google.com/vt/icon/name=icons/spotlight/spotlight-waypoint-b.png&color=ff004C13&psize=16&ay=48&text=' + number
                // url: 'http://mt.google.com/vt/icon/name=icons/spotlight/spotlight-waypoint-blue.png'
            },
            position: gps,
            map: map
        });
    }
}

function syntaxHighlight(json) {
    json = JSON.stringify(reorder(json), undefined, 4);
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'highlight-number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'highlight-key';
            } else {
                cls = 'highlight-string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'highlight-boolean';
        } else if (/null/.test(match)) {
            cls = 'highlight-null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

function reorder(obj){
    if(typeof obj !== 'object')
        return obj
    var temp = {};
    var keys = [];
    for(var key in obj)
        keys.push(key);
    keys.sort();
    for(var index in keys)
        temp[keys[index]] = reorder(obj[keys[index]]);
    return temp;
}


function insidePoly(poly, test)
{
    var mugu_polygon = [
        [36.84760358494509,-1.327081544529206],
        [36.89582228098138,-1.359345639801114],
        [36.91977612521943,-1.381966878596614],
        [36.94217512814311,-1.403520649350417],
        [36.96222324781215,-1.4400383096453],
        [36.96220937004082,-1.444560752347773],
        [36.93074624450506,-1.429101257073484],
        [36.92088994113633,-1.414716462920922],
        [36.90062300775902,-1.414175015784091],
        [36.87104523185378,-1.406720257763014],
        [36.84554325722971,-1.391551003367723],
        [36.83570445212342,-1.389158319389488],
        [36.82266258214148,-1.38543366306295],
        [36.80679374059817,-1.389168693769334],
        [36.772596148744,-1.388909767344104],
        [36.77049832998264,-1.38121562081811],
        [36.76191950818965,-1.355269851938948],
        [36.767134199668,-1.341181597630497],
        [36.77531856173233,-1.336916405472111],
        [36.79848129016496,-1.334923627374748],
        [36.84760358494509,-1.327081544529206],
    ];
    poly = undef(poly, mugu_polygon);
    var nvert = poly.length;
    var c = false;
    for (var i = 0, j = nvert - 1; i < nvert; j = i++)
        if ( ((poly[i][1] > test[1]) != (poly[j][1] > test[1])) &&
        (test[0] < (poly[j][0]-poly[i][0]) * (test[1]-poly[i][1]) / (poly[j][1]-poly[i][1]) + poly[i][0]) )
            c = !c;
    return c
}
