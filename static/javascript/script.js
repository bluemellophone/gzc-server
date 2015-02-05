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

function submitPDF(nonce)
{
    var documents = {};
    $('.printarea-document').not('.no-email-address').each(function( index, element ) {
        var mail = $(element).attr('email-mail');
        var attachment = $(element).attr('email-attachment');
        if(mail != "" && attachment != "")
        {
        console.log("PROCESSING PRINTAREA " + mail + " " + attachment);
            content = '<head>' + $('head').html() + '</head><body><div class="printarea">' + $(element).html() + '</div></body>';
            documents['content-' + mail + '-' + attachment] = content;
//          documents['content-' + mail + '-' + attachment] = '';
            documents['email-' + mail + '-' + attachment] = $(element).attr('email-address');
            documents['name-' + mail + '-' + attachment] = $(element).attr('email-name');
            documents['cc-emails-' + mail + '-' + attachment] = $(element).attr('cc-email-addresses');
            documents['type-' + mail + '-' + attachment] = $(element).attr('email-type');
            documents['orderid-' + mail + '-' + attachment] = $(element).attr('order-id');
            documents['entityid-' + mail + '-' + attachment] = $(element).attr('entity-id');
            documents['filename-' + mail + '-' + attachment] = $(element).attr('email-attachment-filename');
        }
    });
    
    $('.printarea-document-attachment').not('.no-email-address').each(function( index, element ) {
        var mail = $(element).attr('email-mail');
        var attachment = $(element).attr('email-attachment');
        if(mail != "" && attachment != "")
        {
            documents['content-' + mail + '-' + attachment] = $(element).attr('email-attachment-source');
            documents['email-' + mail + '-' + attachment] = $(element).attr('email-address');
            documents['name-' + mail + '-' + attachment] = $(element).attr('email-name');
            documents['type-' + mail + '-' + attachment] = $(element).attr('email-type');
            documents['orderid-' + mail + '-' + attachment] = $(element).attr('order-id');
            documents['filename-' + mail + '-' + attachment] = $(element).attr('email-attachment-filename');
        }
    });

    if(Object.keys(documents).length > 0)
    { 
//      console.log("SENT: " + JSON.stringify(documents));
        $('.sending-overlay-notice').css('visibility', 'visible');
        disable_scroll();
        temp = document.title.split(" - ");
        if(temp.length == 2)
        {
        document.title = temp[1];   
        }
        document.title = "Sending - " + document.title;
        
        $.ajax({
          type: "POST",
          url: '/account/account-pdf.php?nonce=' + nonce,
          data: documents,
        })
        .done(function(response) {
            $('.sending-overlay-notice').css('visibility', 'hidden');
            enable_scroll();
        temp = document.title.split(" - ");
        if(temp.length == 2)
        {
        document.title = temp[1];   
        }
        document.title = "Sent - " + document.title;
/*          console.log("RESPONSE: " + response); */
        })
        .fail(function(response) { 
            alert("FAILURE GENERATING PDF FILE - " + JSON.stringify(response));
            $('.sending-overlay-notice').css('visibility', 'hidden');
            enable_scroll();
        document.title = "Failed - ADK Scheduler";
        });
    }
}

function loadGPSMap(track, markers, center)
{
    var center = new google.maps.LatLng(-1.364107, 36.850548);

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

    // Place a marker
    new google.maps.Marker({
        position: center,
        map: map
    });
    
    var track = new Array();
    for (var i = 0; i < 20; i++) {
        lat = -1.3817505 + Math.random() * 0.06 - 0.03;
        lon = 36.8236284 + Math.random() * 0.06 - 0.03;
        track[i] = new google.maps.LatLng(lat, lon);
    }

    new google.maps.Polyline({
        path: track,
        strokeColor: "#428BCA",
        strokeOpacity: 1.0,
        strokeWeight: 2,
        map: map
    });

}