SELECT
    E.Firstname
    , E.Lastname
    , S.PositionName
    , E.DateofBirth
    , S.Salary
    , EXTRACT(YEAR FROM AGE(E.DateofBirth)) AS Age

FROM EMPLOYEE AS E
JOIN SALARY AS S
    ON E.PositionID = S.PositionID
WHERE EXTRACT(YEAR FROM E.DateofBirth) BETWEEN 1990 AND 1992
ORDER BY EXTRACT(YEAR FROM AGE(E.DateofBirth)) ASC, S.Salary DESC
;


WITH All_Bouns AS (
    SELECT EmpID, BonusAmount FROM Bonus
    UNION ALL
    SELECT EmpID, BonusAmount FROM Bonus_Backup
) 

SELECT
    E.Firstname || ' ' || E.Lastname AS Name
    , S.PositionName
    , S.Salary
    , COALESCE(SUM(AB.BonusAmount), 0) AS "All Year Total Bonus"
FROM EMPLOYEE AS E
JOIN SALARY AS S
    ON E.PositionID = S.PositionID
LEFT JOIN All_Bouns AS AB
    ON E.EmpID = AB.EmpID
GROUP BY
    E.EmpID,
    E.Firstname,
    E.Lastname,
    S.PositionName,
    S.Salary
ORDER BY E.EmpID ASC
;


WITH All_Bonus AS (
    SELECT EmpID, BonusDate, BonusAmount FROM Bonus
    UNION ALL
    SELECT EmpID, BonusDate, BonusAmount FROM Bonus_Backup
)


SELECT
    E.Firstname,
    E.Lastname,
    B.BonusAmount
FROM EMPLOYEE AS E
JOIN All_Bonus AS B
    ON E.EmpID = B.EmpID
WHERE EXTRACT(YEAR FROM B.BonusDate) = 2022
    AND E.EmpID NOT IN (
        SELECT EmpID 
        FROM All_Bonus
        WHERE EXTRACT(YEAR FROM BonusDate) = 2020
    )
ORDER BY E.Firstname ASC, B.BonusAmount ASC
;


WITH All_Bonus AS (
    SELECT EmpID, BonusDate, BonusAmount FROM Bonus
    UNION ALL
    SELECT EmpID, BonusDate, BonusAmount FROM Bonus_Backup
),
Yearly_Bonus AS (
    SELECT
        EXTRACT(YEAR FROM BonusDate) AS BonusYear
        , EmpID
        , BonusAmount
        , MAX(BonusAmount) OVER (PARTITION BY EXTRACT(YEAR FROM BonusDate)) AS MaxBonus
        , MIN(BonusAmount) OVER (PARTITION BY EXTRACT(YEAR FROM BonusDate)) AS MinBonus
    FROM All_Bonus
)

SELECT
    YB.BonusYear
    , E.Firstname
    , E.Lastname
    , YB.BonusAmount
FROM Yearly_Bonus AS YB
JOIN EMPLOYEE AS E
    ON YB.EmpID = E.EmpID
WHERE YB.BonusAmount = YB.MaxBonus OR YB.BonusAmount = YB.MinBonus
ORDER BY YB.BonusYear DESC, YB.BonusAmount DESC
;