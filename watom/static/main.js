"use strict";

let socket;

function redraw() {
    document.body.innerHTML = watomState.page;
}

function connect() {
    socket = new WebSocket('ws://' + location.host + '/api/' + watomState.page_id);

    socket.addEventListener('open', function (event) {
        console.log('Connection established');
    });

    socket.addEventListener('message', function (event) {
        console.log('Message from server ', event.data);

        let data = JSON.parse(event.data);
        watomState.page = data.page;
        redraw();
    });

    socket.addEventListener('close', function (event) {
        console.log('Connection closed');
        setTimeout(connect, 5000);
    });
}

function initialize() {
    redraw();

    connect();
}

if (document.readyState == "loading") {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}
