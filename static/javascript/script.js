function submit_cookie(name, value) {
  $.ajax({
      url: "/ajax/cookie.html?name=" + name + "&value=" + value,
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

function removeFromArray(value, array)
{
    var index = array.indexOf(value);
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

    // Initialize the Google Maps API v3
    var map = new google.maps.Map(document.getElementById('gps-map-canvas'), {
        zoom: 12,
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

    var track_path = new Array();
    for (var index in track)
    {
        marker = track[index];
        gps = new google.maps.LatLng(marker[0], marker[1]);
        track_path.push(gps);
    }

    new google.maps.Polyline({
        path: track_path,
        strokeColor: "#428BCA",
        strokeOpacity: 1.0,
        strokeWeight: 2,
        map: map
    });

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
