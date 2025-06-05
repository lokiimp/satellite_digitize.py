from PIL import Image
for i in range(2,26):
    img = Image.open(rf"images\test{i}.tif")
    width, height = img.size
    img_text = img.crop((0,0,width,height/10))
    #img_text.show()
    img_text.save(rf"C:\Users\lokii\Documents\trainingdata\eng_pixelfont.exp{i-1}.tif")
