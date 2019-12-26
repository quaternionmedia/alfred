function seconds(t) {
  t = t.split(":")
  // console.log('splitting', t)
  var v = 3600*parseInt(t[0]) + 60*parseInt(t[1]) + parseInt(t[2])
  // console.log('v', v)
  return v
}

export const csvStringToArray = strData =>
{
    const objPattern = new RegExp(("(\\,|\\r?\\n|\\r|^)(?:\"([^\"]*(?:\"\"[^\"]*)*)\"|([^\\,\\r\\n]*))"),"gi");
    let arrMatches = null, arrData = [[]];
    while (arrMatches = objPattern.exec(strData)){
        if (arrMatches[1].length && arrMatches[1] !== ",")arrData.push([]);
        arrData[arrData.length - 1].push(arrMatches[2] ?
            arrMatches[2].replace(new RegExp( "\"\"", "g" ), "\"") :
            arrMatches[3]);
    }
    arrData = arrData.slice(1)

    for (var i = 0; i < arrData.length; i++) {
      arrData[i] = arrData[i].map(col => col.includes(":") && !col.includes("M") ? seconds(col) : col
      )
    }
    console.log(arrData)
  // )
    // return arrData.includes(":") ? seconds(arrData) : arrData;
    return arrData
}
