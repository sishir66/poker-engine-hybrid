const ROWS = 6;
const COLS = 5;
const board = document.getElementById("board")


// building empty grid
for (let r = 0; r < ROWS; r++)
{
    const row = document.createElement("div")
    row.className = "row";
    for (let c = 0; c < COLS; c++)
    {
        const tile = document.createElement("div");
        tile.className = "tile";
        tile.textContent = "";
        row.appendChild(tile);
    }
    board.appendChild(row);
}

const guessInput = document.getElementById("guess");
const submitButton = document.getElementById("submit");

let currentRow = 0; // start with row 0 or the first



submitButton.addEventListener("click", () => {
    const guess = String(guessInput.value).toLowerCase();

    if (guess.length !== 5)
    {
        alert("Guess must be 5 letters!")
        return
    }
    const row = board.children[currentRow]; // get current row

    let arrayOfTarget = targetWord.split("");
    let arrayOfGreens = [];
    let arrayOfGuess = guess.split("")
    for (let i =0; i < 5; i++)
    {
        const tile = row.children[i];
        if (arrayOfGuess[i] === arrayOfTarget[i])
        {
            tile.style.backgroundColor = "green";
            arrayOfTarget[i] = null;
            arrayOfGuess[i] = null;
            arrayOfGreens.push(i)
        }
    }
    for (let i = 0; i < 5; i++)
    {
        const tile = row.children[i];
        if (arrayOfGuess[i] !== null)
        {
            if (arrayOfTarget.includes(arrayOfGuess[i]))
            {
                tile.style.backgroundColor = "yellow";
                let firstOccuranceIndex = arrayOfTarget.indexOf(arrayOfGuess[i]);
                arrayOfTarget[firstOccuranceIndex] = null;
            }
            else 
            {
                tile.style.backgroundColor = "gray";
            }

        }
    }

    for (let i= 0; i <5; i++) 
    {
        row.children[i].textContent=guess[i] // loop within each row and put letter in tile
    }

    currentRow++; // move to next row for next guess
    guessInput.value = ""; // clear input
});
