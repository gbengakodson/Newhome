// signature-pad.js
class SignaturePad {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.drawing = false;
        this.lastX = 0;
        this.lastY = 0;

        // Set default styles
        this.ctx.strokeStyle = options.penColor || '#000000';
        this.ctx.lineWidth = options.penWidth || 2;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';

        this.bindEvents();
    }

    bindEvents() {
        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseleave', () => this.stopDrawing());

        // Touch events for mobile
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startDrawing(e.touches[0]);
        });
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            this.draw(e.touches[0]);
        });
        this.canvas.addEventListener('touchend', () => this.stopDrawing());
    }

    startDrawing(e) {
        this.drawing = true;
        const pos = this.getPosition(e);
        this.lastX = pos.x;
        this.lastY = pos.y;
        this.ctx.beginPath();
    }

    draw(e) {
        if (!this.drawing) return;
        e.preventDefault();

        const pos = this.getPosition(e);
        const currentX = pos.x;
        const currentY = pos.y;

        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(currentX, currentY);
        this.ctx.stroke();

        this.lastX = currentX;
        this.lastY = currentY;
    }

    stopDrawing() {
        this.drawing = false;
        this.ctx.closePath();
    }

    getPosition(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    toDataURL() {
        return this.canvas.toDataURL('image/png');
    }

    isEmpty() {
        const pixels = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height).data;
        for (let i = 0; i < pixels.length; i += 4) {
            if (pixels[i + 3] !== 0) return false; // Found a non-transparent pixel
        }
        return true;
    }
}