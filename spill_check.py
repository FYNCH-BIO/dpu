#!/usr/bin/env python3


from statistics import stdev


def spill_check(data):
    data = float(data)
    size = len(tempWindow)
    global spillCount
    if (size < 10):
        tempWindow.append(data)
    if (size == 10):
        #calculate moving average and z-score for new data point
        avg = sum(tempWindow) / len(tempWindow)
        std = stdev(tempWindow)
        diff = abs((abs(data) - avg))
        z_score = diff / std
        print("Data: ", data)
        print("Z-score: " , z_score)
        print("Std: ", std)
        print("Average: ", avg)
        if (z_score > 10 and std >= 0.04 and diff > 2):
            print('Potential spill detected in vial')
            spillCount += 1
        #elif (data < 0):
        #    spillCount += 1
        else:
            tempWindow.append(data)
            tempWindow.pop(0)
        if (spillCount == 3):
            return True

if __name__ == '__main__':
    tempWindow = []
    detect = False
    lineNum = 0
    spillCount = 0
    with open("/Users/ezirayimerwolle/Desktop/KhalilLab_Notes/Data/No_Spills/Exp1/vial15_temp.txt") as f:
        for line in f:
            temp = line.split(',')
            data = temp[1]
            detect = spill_check(data)
            print(tempWindow)
            print("Spill Count: ", spillCount)
            print('\n')

            if spillCount == 3:
                print(lineNum)
                break
            lineNum = lineNum + 1
        if spillCount < 3:
            print("No spill detected")
