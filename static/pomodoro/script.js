let pomodoro = document.getElementById("pomodoro-timer")
let short = document.getElementById("short-timer")
let long = document.getElementById("long-timer")
let timers = document.querySelectorAll(".timer-display")
let session = document.getElementById("pomodoro-session")
let shortBreak = document.getElementById("short-break")
let longBreak = document.getElementById("long-break")
let startBtn = document.getElementById("start")
let stopBtn = document.getElementById("stop")
let timerMsg = document.getElementById("timer-message")
let taskInput = document.getElementById("task-input")
let taskDisplay = document.getElementById("task-name-display")

let currentTimer = null
let myInterval = null

function showDefaultTimer() {
    pomodoro.style.display = "block"
    short.style.display = "none"
    long.style.display = "none"
    taskInput.style.display = "block"
    taskDisplay.textContent = ""
}

showDefaultTimer()

function hideAll() {
    timers.forEach(timer => timer.style.display = "none")
}

function resetUI() {
    taskInput.style.display = "block"
    taskDisplay.textContent = ""
    clearInterval(myInterval)
}

session.addEventListener("click", () => {
    hideAll()
    pomodoro.style.display = "block"
    session.classList.add("active")
    shortBreak.classList.remove("active")
    longBreak.classList.remove("active")
    currentTimer = pomodoro
    resetUI()
})

shortBreak.addEventListener("click", () => {
    hideAll()
    short.style.display = "block"
    session.classList.remove("active")
    shortBreak.classList.add("active")
    longBreak.classList.remove("active")
    currentTimer = short
    resetUI()
})

longBreak.addEventListener("click", () => {
    hideAll()
    long.style.display = "block"
    session.classList.remove("active")
    shortBreak.classList.remove("active")
    longBreak.classList.add("active")
    currentTimer = long
    resetUI()
})

function startTimer(timerDisplay) {
    if (myInterval) clearInterval(myInterval)

    let timerDuration = timerDisplay.getAttribute("data-duration").split(":")[0]
    let durationInMilliseconds = timerDuration * 60 * 1000
    let endTimestamp = Date.now() + durationInMilliseconds

    myInterval = setInterval(() => {
        const timeRemaining = endTimestamp - Date.now()

        if (timeRemaining <= 0) {
            clearInterval(myInterval)
            timerDisplay.textContent = "00:00"
            const alarm = new Audio("https://www.freespecialeffects.co.uk/soundfx/scifi/electronic.wav")
            alarm.play()
            taskInput.style.display = "block"
        } else {
            const minutes = Math.floor(timeRemaining / 60000)
            const seconds = ((timeRemaining % 60000) / 1000).toFixed(0)
            timerDisplay.textContent = `${minutes}:${seconds.toString().padStart(2, "0")}`
        }
    }, 1000)
}

startBtn.addEventListener("click", () => {
    if (currentTimer) {
        taskDisplay.textContent = taskInput.value || "No task specified"
        taskInput.style.display = "none"
        startTimer(currentTimer)
        timerMsg.style.display = "none"
    } else {
        timerMsg.style.display = "block"
    }
})

stopBtn.addEventListener("click", () => {
    if (currentTimer) {
        clearInterval(myInterval)
        taskInput.style.display = "block"
    }
})
