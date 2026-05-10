const canvas = document.querySelector("#snake-board");
const ctx = canvas.getContext("2d");
const scoreEl = document.querySelector("#score");
const bestScoreEl = document.querySelector("#best-score");
const statusEl = document.querySelector("#status");
const startButton = document.querySelector("#start-button");
const pauseButton = document.querySelector("#pause-button");
const pad = document.querySelector(".snake-pad");

const gridSize = 21;
const cellSize = canvas.width / gridSize;
const storageKey = "my-dashboard:game-lab:snake-best";
const tickMs = 115;

let snake;
let apple;
let direction;
let queuedDirection;
let score;
let bestScore = Number(localStorage.getItem(storageKey) || "0");
let timer = null;
let running = false;
let paused = false;

bestScoreEl.textContent = String(bestScore);

function startGame() {
  snake = [
    { x: 10, y: 10 },
    { x: 9, y: 10 },
    { x: 8, y: 10 },
  ];
  direction = { x: 1, y: 0 };
  queuedDirection = direction;
  score = 0;
  running = true;
  paused = false;
  scoreEl.textContent = "0";
  statusEl.textContent = "Eat apples. Avoid walls and yourself.";
  placeApple();
  draw();
  restartTimer();
}

function restartTimer() {
  window.clearInterval(timer);
  timer = window.setInterval(tick, tickMs);
}

function stopTimer() {
  window.clearInterval(timer);
  timer = null;
}

function togglePause() {
  if (!running) {
    return;
  }
  paused = !paused;
  statusEl.textContent = paused ? "Paused." : "Back in motion.";
}

function tick() {
  if (!running || paused) {
    return;
  }

  direction = queuedDirection;
  const head = snake[0];
  const nextHead = { x: head.x + direction.x, y: head.y + direction.y };

  if (hitWall(nextHead) || hitSnake(nextHead)) {
    endGame();
    return;
  }

  snake.unshift(nextHead);

  if (nextHead.x === apple.x && nextHead.y === apple.y) {
    score += 1;
    scoreEl.textContent = String(score);
    if (score > bestScore) {
      bestScore = score;
      bestScoreEl.textContent = String(bestScore);
      localStorage.setItem(storageKey, String(bestScore));
    }
    placeApple();
  } else {
    snake.pop();
  }

  draw();
}

function endGame() {
  running = false;
  paused = false;
  stopTimer();
  statusEl.textContent = `Game over. Score: ${score}.`;
  draw();
}

function hitWall(point) {
  return point.x < 0 || point.y < 0 || point.x >= gridSize || point.y >= gridSize;
}

function hitSnake(point) {
  return snake.some((segment) => segment.x === point.x && segment.y === point.y);
}

function placeApple() {
  do {
    apple = {
      x: Math.floor(Math.random() * gridSize),
      y: Math.floor(Math.random() * gridSize),
    };
  } while (hitSnake(apple));
}

function setDirection(name) {
  const nextDirections = {
    up: { x: 0, y: -1 },
    down: { x: 0, y: 1 },
    left: { x: -1, y: 0 },
    right: { x: 1, y: 0 },
  };
  const next = nextDirections[name];
  if (!next) {
    return;
  }
  if (!running) {
    startGame();
  }
  if (next.x + direction.x === 0 && next.y + direction.y === 0) {
    return;
  }
  queuedDirection = next;
}

function draw() {
  ctx.fillStyle = "#e9f0e4";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "rgba(48, 85, 50, 0.12)";
  ctx.lineWidth = 1;
  for (let line = 0; line <= gridSize; line += 1) {
    const pos = Math.round(line * cellSize) + 0.5;
    ctx.beginPath();
    ctx.moveTo(pos, 0);
    ctx.lineTo(pos, canvas.height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, pos);
    ctx.lineTo(canvas.width, pos);
    ctx.stroke();
  }

  ctx.fillStyle = "#d63f31";
  drawCell(apple.x, apple.y, 0.62);

  snake.forEach((segment, index) => {
    ctx.fillStyle = index === 0 ? "#1d5f25" : "#2f7d32";
    drawCell(segment.x, segment.y, 0.82);
  });
}

function drawCell(x, y, scale) {
  const inset = (cellSize * (1 - scale)) / 2;
  ctx.beginPath();
  ctx.roundRect(
    x * cellSize + inset,
    y * cellSize + inset,
    cellSize * scale,
    cellSize * scale,
    5,
  );
  ctx.fill();
}

startButton.addEventListener("click", startGame);
pauseButton.addEventListener("click", togglePause);

pad.addEventListener("click", (event) => {
  const button = event.target.closest("[data-direction]");
  if (!button) {
    return;
  }
  setDirection(button.dataset.direction);
});

document.addEventListener("keydown", (event) => {
  const keyMap = {
    ArrowUp: "up",
    ArrowDown: "down",
    ArrowLeft: "left",
    ArrowRight: "right",
    w: "up",
    s: "down",
    a: "left",
    d: "right",
  };
  if (event.key === " " || event.key.toLowerCase() === "p") {
    event.preventDefault();
    togglePause();
    return;
  }
  const directionName = keyMap[event.key] || keyMap[event.key.toLowerCase()];
  if (!directionName) {
    return;
  }
  event.preventDefault();
  setDirection(directionName);
});

startGame();
paused = true;
statusEl.textContent = "Press Start or use arrow keys.";
